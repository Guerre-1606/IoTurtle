import os

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, abort, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

load_dotenv()

BASE = os.path.dirname(os.path.abspath(__file__))

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


@app.route("/<carpeta>/<path:archivo>")
def archivos(carpeta, archivo):
    if carpeta not in ("Css", "Js", "IMG"):
        abort(404)
    return send_from_directory(os.path.join(BASE, carpeta), archivo)

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect("/login?error=sesion")
    return render_template("dashboard.html", usuario=session["usuario"])


if __name__ == "__main__":
    app.run(debug=True)
