import os
import time

import requests

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, abort, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

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


THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{os.getenv('THINGSPEAK_CHANNEL')}/feeds.json"
THINGSPEAK_KEY = os.getenv("THINGSPEAK_READ_KEY")
ultima_sincronizacion = 0


def guardar(envio, cursor):
    valores = []
    for i in range(1, 8):
        v = envio.get(f"field{i}")
        valores.append(float(v) if v not in (None, "") else None)

    recibido = envio["created_at"].replace("T", " ").replace("Z", "")

    cursor.execute(
        "INSERT IGNORE INTO lecturas "
        "(entry_id, recibido, field1, field2, field3, field4, field5, field6, field7) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (envio["entry_id"], recibido, *valores),
    )


def sincronizar():
    global ultima_sincronizacion
    if time.time() - ultima_sincronizacion < 15:
        return
    ultima_sincronizacion = time.time()

    try:
        datos = requests.get(THINGSPEAK_URL, params={"api_key": THINGSPEAK_KEY, "results": 8}, timeout=10).json()
    except Exception as e:
        print("ThingSpeak no responde:", e)
        return

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        for envio in datos.get("feeds", []):
            guardar(envio, cursor)
        conexion.commit()
    finally:
        conexion.close()


def ultimas_lecturas(cantidad=20):
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM lecturas ORDER BY entry_id DESC LIMIT %s", (cantidad,))
        return cursor.fetchall()
    finally:
        conexion.close()

ZONAS = [
    {"nombre": "Soleada",      "temp": "field1", "hum": "field6"},
    {"nombre": "Sombra",       "temp": "field2", "hum": "field7"},
    {"nombre": "Refugio",      "temp": "field3", "hum": None},
    {"nombre": "Intermedia 1", "temp": "field4", "hum": None},
    {"nombre": "Intermedia 2", "temp": "field5", "hum": None},
]

CRITERIOS = {"tmax": 30.0, "tmin": 20.0, "hmin": 60.0}


def numero(valor):
    return float(valor) if valor is not None else None


def evaluar_zona(zona, lectura):
    t = numero(lectura.get(zona["temp"])) if zona["temp"] else None
    h = numero(lectura.get(zona["hum"])) if zona["hum"] else None

    alertas = []
    if t is not None and t > CRITERIOS["tmax"]:
        alertas.append({"tipo": "high", "titulo": f"Temperatura alta · {zona['nombre']}",
                        "detalle": f"{t:.1f} °C supera {CRITERIOS['tmax']:.1f} °C"})
    if t is not None and t < CRITERIOS["tmin"]:
        alertas.append({"tipo": "low", "titulo": f"Temperatura baja · {zona['nombre']}",
                        "detalle": f"{t:.1f} °C bajo {CRITERIOS['tmin']:.1f} °C"})
    if h is not None and h < CRITERIOS["hmin"]:
        alertas.append({"tipo": "low", "titulo": f"Humedad baja · {zona['nombre']}",
                        "detalle": f"{h:.0f} % bajo {CRITERIOS['hmin']:.0f} %"})

    if t is None:
        estado = "none"
    elif any(a["tipo"] == "high" for a in alertas):
        estado = "high"
    elif alertas:
        estado = "low"
    else:
        estado = "ok"

    return {"nombre": zona["nombre"], "temp": t, "hum": h, "estado": estado}, alertas

@app.route("/")
def inicio():
    return render_template("index.html", usuario=session.get("usuario"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "usuario" in session:
            return redirect("/")
        return render_template("login.html")

    correo = request.form.get("correo", "").strip().lower()
    contrasena = request.form.get("contrasena", "")

    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
        usuario = cursor.fetchone()
    finally:
        conexion.close()

    if not usuario or not usuario["contrasena_hash"] or not check_password_hash(usuario["contrasena_hash"], contrasena):
        return redirect("/login?error=credenciales")

    session.clear()
    session["usuario"] = {
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "correo": usuario["correo"],
        "rol": usuario["rol"],
    }
    return redirect("/")


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


@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect("/login?error=sesion")
    return render_template("dashboard.html", usuario=session["usuario"])


@app.route("/api/lecturas")
def api_lecturas():
    if "usuario" not in session:
        return jsonify({"error": "sin sesión"}), 401
    sincronizar()
    filas = ultimas_lecturas()
    for f in filas:
        f["recibido"] = f["recibido"].strftime("%Y-%m-%dT%H:%M:%SZ")
        f["guardado"] = f["guardado"].strftime("%Y-%m-%d %H:%M:%S")
        for i in range(1, 8):
            if f[f"field{i}"] is not None:
                f[f"field{i}"] = float(f[f"field{i}"])
    return jsonify(filas)


@app.route("/api/estado")
def api_estado():
    if "usuario" not in session:
        return jsonify({"error": "sin sesión"}), 401
    sincronizar()

    filas = ultimas_lecturas(1)
    if not filas:
        return jsonify({"ultima": None, "zonas": [], "alertas": [], "kpis": None})
    lectura = filas[0]

    zonas, alertas = [], []
    for zona in ZONAS:
        resultado, alertas_zona = evaluar_zona(zona, lectura)
        zonas.append(resultado)
        alertas.extend(alertas_zona)

    temperaturas = [z["temp"] for z in zonas if z["temp"] is not None]
    kpis = {
        "optimas": sum(1 for z in zonas if z["estado"] == "ok"),
        "total": len(zonas),
        "alertas": len(alertas),
        "gradiente": round(max(temperaturas) - min(temperaturas), 1) if temperaturas else None,
    }

    return jsonify({
        "ultima": lectura["recibido"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_id": lectura["entry_id"],
        "zonas": zonas,
        "alertas": alertas,
        "kpis": kpis,
    })

@app.route("/<carpeta>/<path:archivo>")
def archivos(carpeta, archivo):
    if carpeta not in ("Css", "Js", "IMG"):
        abort(404)
    return send_from_directory(os.path.join(BASE, carpeta), archivo)


if __name__ == "__main__":
    app.run(debug=True)