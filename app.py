from flask import Flask, render_template, send_from_directory, abort

app = Flask(__name__)

@app.route("/")
def inicio():
    return send_from_directory(".", "index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/<carpeta>/<path:archivo>")python3 app.py
def archivos(carpeta, archivo):
    if carpeta not in ("Css", "Js", "IMG"):
        abort(404)
    return send_from_directory(carpeta, archivo)

if __name__ == "__main__":
    app.run(debug=True)