import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import mysql.connector
import pandas as pd
import requests
from dotenv import load_dotenv
from flask import (Flask, Response, abort, g, jsonify, redirect, render_template, request,
                   send_from_directory, session)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "8889")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "ioturtle"),
}


def conectar():
    return mysql.connector.connect(**DB)


# =========================================================
# Qué significa cada field de ThingSpeak
# =========================================================
ZONAS = [
    {"nombre": "Recinto",    "field": "field1"},
    {"nombre": "Soleada",    "field": "field2"},
    {"nombre": "Intermedia", "field": "field3"},
    {"nombre": "Sombra",     "field": "field4"},
]

GENERALES = [
    {"nombre": "Humedad relativa",      "field": "field5", "unidad": "%"},
    {"nombre": "Temperatura del suelo", "field": "field6", "unidad": "°C"},
    {"nombre": "Temperatura ambiente",  "field": "field7", "unidad": "°C"},
]

SENSORES = [
    {"nombre": "Raspberry Pi 4", "funcion": "Nodo de adquisición y envío", "interfaz": "Wi-Fi · MQTT",
     "fields": ["field1", "field2", "field3", "field4", "field5", "field6", "field7"]},
    {"nombre": "MLX90614", "funcion": "Temperatura por zona sin contacto", "interfaz": "I2C",
     "fields": ["field1", "field2", "field3", "field4"]},
    {"nombre": "SHT31", "funcion": "Humedad y temperatura ambiente", "interfaz": "I2C",
     "fields": ["field5", "field7"]},
    {"nombre": "DS18B20", "funcion": "Temperatura del suelo", "interfaz": "1-Wire",
     "fields": ["field6"]},
]

FIELDS = [f"field{i}" for i in range(1, 8)]
NOMBRE_FIELD = {z["field"]: z["nombre"] for z in ZONAS + GENERALES}

CRITERIOS_DEFECTO = {"tmax": 30.0, "tmin": 20.0, "hmin": 60.0}

RANGOS = {
    "6h":  {"texto": "6 horas",  "delta": timedelta(hours=6),  "grupo": "5min"},
    "24h": {"texto": "24 horas", "delta": timedelta(hours=24), "grupo": "15min"},
    "7d":  {"texto": "7 días",   "delta": timedelta(days=7),   "grupo": "1h"},
    "30d": {"texto": "30 días",  "delta": timedelta(days=30),  "grupo": "6h"},
}

HORA_COLOMBIA = timedelta(hours=-5)
MINUTOS_SIN_DATOS = 2
CORTE_EPISODIO = timedelta(minutes=5)
TOLERANCIA_EPISODIO = timedelta(minutes=10)


def ahora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =========================================================
# Configuración de cada usuario (canal, clave y límites)
# =========================================================
def consultar(sql, datos=()):
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(sql, datos)
        return cursor.fetchall()
    finally:
        conexion.close()


def ejecutar(sql, datos=()):
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute(sql, datos)
        conexion.commit()
    finally:
        conexion.close()


def mi_config():
    if "config" not in g:
        filas = consultar("SELECT * FROM configuracion_usuario WHERE usuario_id = %s", (session["usuario"]["id"],))
        g.config = filas[0] if filas else None
    return g.config


def configurado():
    if "usuario" not in session:
        return False
    c = mi_config()
    return bool(c and c["canal"] and c["read_key"])


def mi_canal():
    return mi_config()["canal"]


def guardar_config(**campos):
    usuario_id = session["usuario"]["id"]
    existe = consultar("SELECT usuario_id FROM configuracion_usuario WHERE usuario_id = %s", (usuario_id,))
    columnas = list(campos)
    if existe:
        asignaciones = ", ".join(f"{c} = %s" for c in columnas)
        ejecutar(f"UPDATE configuracion_usuario SET {asignaciones} WHERE usuario_id = %s",
                 (*campos.values(), usuario_id))
    else:
        marcas = ", ".join(["%s"] * (len(columnas) + 1))
        ejecutar(f"INSERT INTO configuracion_usuario (usuario_id, {', '.join(columnas)}) VALUES ({marcas})",
                 (usuario_id, *campos.values()))
    g.pop("config", None)


def obtener_criterios():
    c = mi_config() or {}
    return {clave: float(c[clave]) if c.get(clave) is not None else valor
            for clave, valor in CRITERIOS_DEFECTO.items()}


# =========================================================
# ThingSpeak → MySQL
# =========================================================
THINGSPEAK_URL = "https://api.thingspeak.com/channels/{canal}/feeds.json"
ultima_sincronizacion = {}


def pedir_thingspeak(canal, read_key, resultados):
    respuesta = requests.get(THINGSPEAK_URL.format(canal=canal),
                             params={"api_key": read_key, "results": resultados}, timeout=10)
    datos = respuesta.json()
    if not isinstance(datos, dict) or "channel" not in datos:
        return None
    return datos


def guardar(envio, cursor, canal):
    valores = []
    for field in FIELDS:
        v = envio.get(field)
        valores.append(float(v) if v not in (None, "") else None)

    recibido = envio["created_at"].replace("T", " ").replace("Z", "")

    cursor.execute(
        "INSERT IGNORE INTO lecturas "
        "(canal, entry_id, recibido, field1, field2, field3, field4, field5, field6, field7) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (canal, envio["entry_id"], recibido, *valores),
    )


def sincronizar():
    c = mi_config()
    canal = c["canal"]
    if time.time() - ultima_sincronizacion.get(canal, 0) < 15:
        return
    ultima_sincronizacion[canal] = time.time()

    try:
        datos = pedir_thingspeak(canal, c["read_key"], 100)
    except Exception as e:
        print("ThingSpeak no responde:", e)
        return
    if not datos:
        return

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        for envio in datos.get("feeds", []):
            guardar(envio, cursor, canal)
        conexion.commit()
    finally:
        conexion.close()


# =========================================================
# Lecturas desde MySQL (solo las del canal del usuario)
# =========================================================
def ultimas_lecturas(cantidad=20):
    return consultar("SELECT * FROM lecturas WHERE canal = %s ORDER BY recibido DESC LIMIT %s",
                     (mi_canal(), cantidad))


def lecturas_df(desde=None, limite=None):
    columnas = "entry_id, recibido, " + ", ".join(FIELDS)
    if limite:
        filas = consultar(f"SELECT {columnas} FROM lecturas WHERE canal = %s ORDER BY recibido DESC LIMIT %s",
                          (mi_canal(), limite))
        filas.reverse()
    else:
        filas = consultar(f"SELECT {columnas} FROM lecturas WHERE canal = %s AND recibido >= %s ORDER BY recibido",
                          (mi_canal(), desde))

    df = pd.DataFrame(filas, columns=["entry_id", "recibido"] + FIELDS)
    df["recibido"] = pd.to_datetime(df["recibido"])
    for field in FIELDS:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    return df


def rango_pedido():
    clave = request.args.get("rango", "24h")
    return clave if clave in RANGOS else "24h"


# =========================================================
# Estado actual (vista general, mapa y número de alertas)
# =========================================================
def numero(valor):
    return float(valor) if valor is not None else None


def evaluar_zona(zona, lectura, c):
    t = numero(lectura.get(zona["field"]))

    alertas = []
    if t is not None and t > c["tmax"]:
        alertas.append({"tipo": "high", "titulo": f"Temperatura alta · {zona['nombre']}",
                        "detalle": f"{t:.1f} °C supera {c['tmax']:.1f} °C"})
    if t is not None and t < c["tmin"]:
        alertas.append({"tipo": "low", "titulo": f"Temperatura baja · {zona['nombre']}",
                        "detalle": f"{t:.1f} °C bajo {c['tmin']:.1f} °C"})

    if t is None:
        estado = "none"
    elif alertas:
        estado = alertas[0]["tipo"]
    else:
        estado = "ok"

    return {"nombre": zona["nombre"], "field": zona["field"], "temp": t, "estado": estado}, alertas


def evaluar_generales(lectura, c):
    generales, alertas = [], []
    for g in GENERALES:
        valor = numero(lectura.get(g["field"]))
        estado = "none" if valor is None else "ok"

        if g["field"] == "field5" and valor is not None and valor < c["hmin"]:
            estado = "low"
            alertas.append({"tipo": "low", "titulo": "Humedad baja · Recinto",
                            "detalle": f"{valor:.0f} % bajo {c['hmin']:.0f} %"})

        generales.append({"nombre": g["nombre"], "field": g["field"], "valor": valor,
                          "unidad": g["unidad"], "estado": estado})
    return generales, alertas


def calcular_estado():
    sincronizar()
    c = obtener_criterios()

    filas = ultimas_lecturas(1)
    if not filas:
        return {"ultima": None, "zonas": [], "generales": [], "alertas": [], "kpis": None, "criterios": c}
    lectura = filas[0]

    zonas, alertas = [], []
    for zona in ZONAS:
        resultado, alertas_zona = evaluar_zona(zona, lectura, c)
        zonas.append(resultado)
        alertas.extend(alertas_zona)

    generales, alertas_generales = evaluar_generales(lectura, c)
    alertas.extend(alertas_generales)

    temperaturas = [z["temp"] for z in zonas if z["temp"] is not None]
    kpis = {
        "optimas": sum(1 for z in zonas if z["estado"] == "ok"),
        "total": len(zonas),
        "alertas": len(alertas),
        "gradiente": round(max(temperaturas) - min(temperaturas), 1) if temperaturas else None,
    }

    return {
        "ultima": lectura["recibido"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_id": lectura["entry_id"],
        "zonas": zonas,
        "generales": generales,
        "alertas": alertas,
        "kpis": kpis,
        "criterios": c,
    }


# =========================================================
# Cálculos con pandas: alertas por episodios y reportes
# =========================================================
def episodios_alerta(df, c):
    if df.empty:
        return []

    variables = [(z["field"], z["nombre"], "temp") for z in ZONAS] + [("field5", "Recinto", "hum")]
    salto = df["recibido"].diff() > CORTE_EPISODIO
    episodios = []

    for field, zona, clase in variables:
        valores = df[field]
        estado = pd.Series("ok", index=df.index)
        if clase == "temp":
            estado[valores > c["tmax"]] = "high"
            estado[valores < c["tmin"]] = "low"
        else:
            estado[valores < c["hmin"]] = "low"
        estado[valores.isna()] = "none"

        grupo = ((estado != estado.shift()) | salto).cumsum()
        bloques = []
        for _, bloque in df.groupby(grupo):
            tipo = estado[bloque.index[0]]
            if tipo not in ("high", "low"):
                continue
            serie = bloque[field]
            bloques.append({
                "tipo": tipo,
                "inicio": bloque["recibido"].iloc[0].to_pydatetime(),
                "fin": bloque["recibido"].iloc[-1].to_pydatetime(),
                "extremo": serie.max() if tipo == "high" else serie.min(),
                "lecturas": len(bloque),
            })

        unidos = []
        for bloque in bloques:
            anterior = unidos[-1] if unidos else None
            if anterior and anterior["tipo"] == bloque["tipo"] and bloque["inicio"] - anterior["fin"] <= TOLERANCIA_EPISODIO:
                anterior["fin"] = bloque["fin"]
                anterior["lecturas"] += bloque["lecturas"]
                anterior["extremo"] = (max if bloque["tipo"] == "high" else min)(anterior["extremo"], bloque["extremo"])
            else:
                unidos.append(dict(bloque))

        for e in unidos:
            if clase == "temp":
                limite = c["tmax"] if e["tipo"] == "high" else c["tmin"]
                e["titulo"] = f"Temperatura {'alta' if e['tipo'] == 'high' else 'baja'} · {zona}"
                e["detalle"] = f"Extremo {e['extremo']:.1f} °C (límite {limite:.1f} °C)"
            else:
                e["titulo"] = f"Humedad baja · {zona}"
                e["detalle"] = f"Mínimo {e['extremo']:.0f} % (límite {c['hmin']:.0f} %)"
            e["duracion"] = e["fin"] - e["inicio"]
            episodios.append(e)

    episodios.sort(key=lambda e: e["inicio"], reverse=True)
    return episodios


def resumen_reporte(df, c):
    campos_zona = [z["field"] for z in ZONAS]
    variables = []
    for item in ZONAS + GENERALES:
        field = item["field"]
        serie = df[field].dropna()

        if field in campos_zona:
            en_rango = serie.between(c["tmin"], c["tmax"])
        elif field == "field5":
            en_rango = serie >= c["hmin"]
        else:
            en_rango = None

        variables.append({
            "nombre": item["nombre"],
            "unidad": item.get("unidad", "°C"),
            "lecturas": int(serie.count()),
            "minimo": serie.min() if len(serie) else None,
            "maximo": serie.max() if len(serie) else None,
            "promedio": serie.mean() if len(serie) else None,
            "desviacion": serie.std() if len(serie) > 1 else None,
            "en_rango": en_rango.mean() * 100 if en_rango is not None and len(serie) else None,
        })

    zonas = df[campos_zona]
    gradiente = (zonas.max(axis=1) - zonas.min(axis=1)).dropna()

    return {
        "variables": variables,
        "lecturas": len(df),
        "desde": df["recibido"].min().to_pydatetime() if not df.empty else None,
        "hasta": df["recibido"].max().to_pydatetime() if not df.empty else None,
        "gradiente_promedio": gradiente.mean() if len(gradiente) else None,
        "gradiente_maximo": gradiente.max() if len(gradiente) else None,
    }


# =========================================================
# Ayudas para las plantillas
# =========================================================
@app.template_filter("hora_local")
def hora_local(fecha, formato="%d/%m %I:%M %p"):
    if fecha is None:
        return "--"
    return (fecha + HORA_COLOMBIA).strftime(formato).replace("AM", "a. m.").replace("PM", "p. m.")


@app.template_filter("duracion")
def formato_duracion(delta):
    minutos = int(delta.total_seconds() // 60)
    if minutos < 1:
        return "menos de 1 min"
    if minutos < 60:
        return f"{minutos} min"
    horas, minutos = divmod(minutos, 60)
    return f"{horas} h {minutos} min"


@app.template_filter("num")
def formato_numero(valor, decimales=1):
    if valor is None or pd.isna(valor):
        return "--"
    return f"{valor:.{decimales}f}"


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "sin sesión"}), 401
            return redirect("/login?error=sesion")
        return vista(*args, **kwargs)
    return envoltura


PAGINAS = {
    "dashboard": ("general", "Vista general"),
    "mapa": ("mapa", "Mapa del recinto"),
    "tiempo_real": ("tiempo", "Tiempo real"),
    "historico": ("historico", "Histórico"),
    "alertas": ("alertas", "Alertas"),
    "reportes": ("reportes", "Reportes"),
    "reportes_csv": ("reportes", "Reportes"),
    "dispositivos": ("dispositivos", "Dispositivos"),
}


def config_requerida(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not configurado():
            if request.path.startswith("/api/"):
                return jsonify({"error": "sin_configurar"}), 409
            nombre, titulo = PAGINAS.get(request.endpoint, ("general", "Dashboard"))
            return render_template("sin_configurar.html", usuario=session["usuario"], pagina=nombre,
                                   titulo=titulo, n_alertas=0)
        return vista(*args, **kwargs)
    return envoltura


@app.context_processor
def datos_globales():
    return {"configurado": configurado()}


def pagina(plantilla, nombre, **datos):
    estado = datos.pop("estado", None)
    if estado is None:
        estado = calcular_estado() if configurado() else {"alertas": []}
    return render_template(plantilla, usuario=session["usuario"], pagina=nombre,
                           n_alertas=len(estado["alertas"]), **datos)


# =========================================================
# Portada, login y registro
# =========================================================
@app.route("/")
def inicio():
    return render_template("index.html", usuario=session.get("usuario"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "usuario" in session:
            return redirect("/dashboard")
        return render_template("login.html")

    correo = request.form.get("correo", "").strip().lower()
    contrasena = request.form.get("contrasena", "")

    filas = consultar("SELECT * FROM usuarios WHERE correo = %s", (correo,))
    usuario = filas[0] if filas else None

    if not usuario or not usuario["contrasena_hash"] or not check_password_hash(usuario["contrasena_hash"], contrasena):
        return redirect("/login?error=credenciales")

    session.clear()
    session["usuario"] = {
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "correo": usuario["correo"],
        "rol": usuario["rol"],
    }
    return redirect("/dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login?ok=salida")


@app.route("/registro", methods=["POST"])
def registro():
    nombre = request.form.get("nombre", "").strip()
    correo = request.form.get("correo", "").strip().lower()
    contrasena = request.form.get("contrasena", "")
    confirmar = request.form.get("confirmar", "")

    if not nombre or not correo or len(contrasena) < 8 or contrasena != confirmar:
        return redirect("/login?error=datos#registro")

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return redirect("/login?error=existe")

        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena_hash) VALUES (%s, %s, %s)",
            (nombre, correo, generate_password_hash(contrasena)),
        )
        conexion.commit()
    finally:
        conexion.close()

    return redirect("/login?ok=registrado")


# =========================================================
# Páginas del dashboard
# =========================================================
@app.route("/dashboard")
@login_requerido
@config_requerida
def dashboard():
    return pagina("dashboard.html", "general", zonas=ZONAS)


@app.route("/dashboard/mapa")
@login_requerido
@config_requerida
def mapa():
    return pagina("mapa.html", "mapa")


@app.route("/dashboard/tiempo-real")
@login_requerido
@config_requerida
def tiempo_real():
    return pagina("tiempo_real.html", "tiempo", zonas=ZONAS, generales=GENERALES)


@app.route("/dashboard/historico")
@login_requerido
@config_requerida
def historico():
    return pagina("historico.html", "historico", zonas=ZONAS, generales=GENERALES,
                  rangos=RANGOS, rango=rango_pedido())


@app.route("/dashboard/alertas")
@login_requerido
@config_requerida
def alertas():
    estado = calcular_estado()
    clave = rango_pedido()
    df = lecturas_df(desde=ahora_utc() - RANGOS[clave]["delta"])
    episodios = episodios_alerta(df, estado["criterios"])

    resumen = {
        "total": len(episodios),
        "altas": sum(1 for e in episodios if e["tipo"] == "high"),
        "bajas": sum(1 for e in episodios if e["tipo"] == "low"),
        "tiempo": sum((e["duracion"] for e in episodios), timedelta()),
    }
    return pagina("alertas.html", "alertas", estado=estado, actuales=estado["alertas"],
                  episodios=episodios, resumen=resumen, rangos=RANGOS, rango=clave,
                  criterios=estado["criterios"])


@app.route("/dashboard/reportes")
@login_requerido
@config_requerida
def reportes():
    estado = calcular_estado()
    clave = rango_pedido()
    df = lecturas_df(desde=ahora_utc() - RANGOS[clave]["delta"])
    return pagina("reportes.html", "reportes", estado=estado, reporte=resumen_reporte(df, estado["criterios"]),
                  rangos=RANGOS, rango=clave, criterios=estado["criterios"])


@app.route("/dashboard/reportes.csv")
@login_requerido
@config_requerida
def reportes_csv():
    clave = rango_pedido()
    df = lecturas_df(desde=ahora_utc() - RANGOS[clave]["delta"])

    df[FIELDS] = df[FIELDS].round(2)
    df["recibido"] = (df["recibido"] + HORA_COLOMBIA).dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.rename(columns={"entry_id": "Envío", "recibido": "Hora (Colombia)", **NOMBRE_FIELD})

    nombre = f"ioturtle_{clave}_{(ahora_utc() + HORA_COLOMBIA):%Y%m%d_%H%M}.csv"
    return Response(
        df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@app.route("/dashboard/dispositivos")
@login_requerido
@config_requerida
def dispositivos():
    estado = calcular_estado()
    filas = ultimas_lecturas(1)
    ultima = filas[0] if filas else None

    sensores = []
    for s in SENSORES:
        if ultima is None:
            situacion, texto = "none", "Sin datos"
        else:
            reporta = all(ultima.get(f) is not None for f in s["fields"])
            reciente = ahora_utc() - ultima["recibido"] < timedelta(minutes=MINUTOS_SIN_DATOS)
            if reporta and reciente:
                situacion, texto = "ok", "Activo"
            elif reporta:
                situacion, texto = "low", "Sin datos recientes"
            else:
                situacion, texto = "high", "No reporta"
        sensores.append({**s, "situacion": situacion, "texto": texto,
                         "variables": [NOMBRE_FIELD[f] for f in s["fields"]]})

    totales = consultar("SELECT COUNT(*) AS n, MIN(recibido) AS primera, MAX(recibido) AS ultima "
                        "FROM lecturas WHERE canal = %s", (mi_canal(),))[0]
    return pagina("dispositivos.html", "dispositivos", estado=estado, sensores=sensores, totales=totales,
                  canal=mi_canal(), canal_nombre=mi_config().get("canal_nombre"))


MENSAJES_CONFIG = {
    "perfil": {"ok": "Perfil actualizado.", "nombre": "Escribe tu nombre (máximo 120 caracteres)."},
    "contrasena": {
        "ok": "Contraseña cambiada.",
        "actual": "La contraseña actual no es correcta.",
        "nueva": "La nueva contraseña debe tener mínimo 8 caracteres y coincidir con la confirmación.",
    },
    "dashboard": {
        "ok": "Criterios guardados. Las alertas ya usan los nuevos límites.",
        "numero": "Escribe solo números en los tres campos.",
        "rango": "La temperatura mínima debe ser menor que la máxima, y la humedad debe estar entre 0 y 100.",
    },
    "broker": {
        "ok": "Conexión verificada. El dashboard ya está activo.",
        "canal": "El Channel ID solo lleva números.",
        "key": "Escribe la Read API Key.",
        "credenciales": "ThingSpeak rechazó ese canal o esa clave. Revisa que sea la Read API Key del mismo canal.",
        "red": "No se pudo contactar a ThingSpeak. Revisa tu conexión e intenta de nuevo.",
    },
}


def volver(seccion, codigo):
    clave = "ok" if codigo == "ok" else "error"
    return redirect(f"/dashboard/configuracion?s={seccion}&{clave}={codigo}#{seccion}")


def guardar_perfil():
    nombre = request.form.get("nombre", "").strip()
    if not nombre or len(nombre) > 120:
        return volver("perfil", "nombre")
    ejecutar("UPDATE usuarios SET nombre = %s WHERE id = %s", (nombre, session["usuario"]["id"]))
    session["usuario"] = {**session["usuario"], "nombre": nombre}
    return volver("perfil", "ok")


def guardar_contrasena():
    actual = request.form.get("actual", "")
    nueva = request.form.get("nueva", "")
    confirmar = request.form.get("confirmar", "")

    fila = consultar("SELECT contrasena_hash FROM usuarios WHERE id = %s", (session["usuario"]["id"],))
    guardada = fila[0]["contrasena_hash"] if fila else None
    if not guardada or not check_password_hash(guardada, actual):
        return volver("contrasena", "actual")
    if len(nueva) < 8 or nueva != confirmar:
        return volver("contrasena", "nueva")

    ejecutar("UPDATE usuarios SET contrasena_hash = %s WHERE id = %s",
             (generate_password_hash(nueva), session["usuario"]["id"]))
    return volver("contrasena", "ok")


def guardar_criterios():
    try:
        nuevos = {clave: float(request.form[clave].replace(",", ".")) for clave in ("tmax", "tmin", "hmin")}
    except (KeyError, ValueError):
        return volver("dashboard", "numero")
    if nuevos["tmin"] >= nuevos["tmax"] or not 0 <= nuevos["hmin"] <= 100:
        return volver("dashboard", "rango")
    guardar_config(**nuevos)
    return volver("dashboard", "ok")


def guardar_broker():
    canal = request.form.get("canal", "").strip()
    read_key = request.form.get("read_key", "").strip()
    actual = mi_config() or {}

    if not canal.isdigit() or len(canal) > 20:
        return volver("broker", "canal")
    if not read_key:
        if actual.get("read_key") and actual.get("canal") == canal:
            read_key = actual["read_key"]
        else:
            return volver("broker", "key")

    try:
        datos = pedir_thingspeak(canal, read_key, 1)
    except Exception:
        return volver("broker", "red")
    if not datos:
        return volver("broker", "credenciales")

    guardar_config(canal=canal, read_key=read_key, canal_nombre=datos["channel"].get("name", "")[:120])
    ultima_sincronizacion.pop(canal, None)
    return volver("broker", "ok")


@app.route("/dashboard/configuracion", methods=["GET", "POST"])
@login_requerido
def configuracion():
    if request.method == "POST":
        acciones = {
            "perfil": guardar_perfil,
            "contrasena": guardar_contrasena,
            "dashboard": guardar_criterios,
            "broker": guardar_broker,
        }
        accion = acciones.get(request.form.get("seccion"))
        return accion() if accion else redirect("/dashboard/configuracion")

    perfil = consultar("SELECT nombre, correo, rol, creado, contrasena_hash FROM usuarios WHERE id = %s",
                       (session["usuario"]["id"],))[0]
    config = mi_config() or {}
    clave = config.get("read_key") or ""

    seccion = request.args.get("s")
    codigo = request.args.get("ok") or request.args.get("error")
    mensaje = None
    if seccion in MENSAJES_CONFIG and codigo in MENSAJES_CONFIG[seccion]:
        mensaje = {"seccion": seccion, "ok": "ok" in request.args, "texto": MENSAJES_CONFIG[seccion][codigo]}

    return pagina("configuracion.html", "configuracion",
                  perfil=perfil, tiene_contrasena=bool(perfil["contrasena_hash"]),
                  criterios=obtener_criterios(), zonas=ZONAS, generales=GENERALES,
                  canal=config.get("canal") or "", canal_nombre=config.get("canal_nombre"),
                  clave_oculta=("•" * 8 + clave[-4:]) if clave else "",
                  mensaje=mensaje)


# =========================================================
# APIs que usa el JavaScript
# =========================================================
@app.route("/api/estado")
@login_requerido
@config_requerida
def api_estado():
    return jsonify(calcular_estado())


@app.route("/api/serie")
@login_requerido
@config_requerida
def api_serie():
    sincronizar()
    clave = request.args.get("rango", "live")

    if clave == "live":
        df = lecturas_df(limite=40)
        grupo = None
    else:
        if clave not in RANGOS:
            clave = "24h"
        df = lecturas_df(desde=ahora_utc() - RANGOS[clave]["delta"])
        grupo = RANGOS[clave]["grupo"]
        if not df.empty:
            df = df.set_index("recibido")[FIELDS].resample(grupo).mean().reset_index()

    puntos = []
    for _, fila in df.iterrows():
        punto = {"t": fila["recibido"].strftime("%Y-%m-%dT%H:%M:%SZ")}
        for field in FIELDS:
            punto[field] = None if pd.isna(fila[field]) else round(float(fila[field]), 2)
        puntos.append(punto)

    return jsonify({"rango": clave, "agrupado": grupo, "puntos": puntos, "criterios": obtener_criterios()})


# =========================================================
# Archivos de Css, Js e IMG
# =========================================================
@app.route("/<carpeta>/<path:archivo>")
def archivos(carpeta, archivo):
    if carpeta not in ("Css", "Js", "IMG"):
        abort(404)
    return send_from_directory(os.path.join(BASE, carpeta), archivo)


if __name__ == "__main__":
    app.run(debug=True)
