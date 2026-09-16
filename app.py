"""
Servidor para chatear con Grok, ChatGPT y Claude desde el navegador (compu,
celular, o ya hosteado en internet), reusando toda la lógica de debate.py.
Cada usuario logueado tiene su propia charla privada, independiente de la
de los demás.

Uso local:
    python app.py
Después abrí http://localhost:5050 en la compu, o http://<ip-de-tu-mac>:5050
desde el celular (misma wifi).

Usuarios: se configuran en el .env con la variable USUARIOS, formato
"usuario1:clave1,usuario2:clave2,...". Ver LEEME.txt.
"""
import functools
import hmac
import os
import random
import secrets
import threading
import time

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)

import debate

load_dotenv()

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
if not os.getenv("FLASK_SECRET_KEY"):
    print(
        "⚠️  No hay FLASK_SECRET_KEY en el .env: generé una al vuelo, pero eso "
        "significa que si reiniciás el servidor todos van a tener que volver a "
        "loguearse. Para producción, poné una fija en el .env (ver LEEME.txt)."
    )


def _cargar_usuarios():
    crudo = os.getenv("USUARIOS", "")
    usuarios = {}
    for par in crudo.split(","):
        par = par.strip()
        if ":" in par:
            usuario, clave = par.split(":", 1)
            usuarios[usuario.strip()] = clave.strip()
    return usuarios


USUARIOS = _cargar_usuarios()

_lock = threading.Lock()
_estados = {}  # usuario -> estado de su charla (cada uno la suya)


def _estado_nuevo():
    return {
        "tema": None,
        "historial": "",
        "mensajes": [],  # [{"autor": ..., "texto": ..., "cierre": bool}]
        "turno": 0,
        "cerrado": False,
        "archivo_plan": None,
    }


def estado_actual():
    usuario = session["usuario"]
    return _estados.setdefault(usuario, _estado_nuevo())


def requiere_login(vista):
    @functools.wraps(vista)
    def envoltorio(*args, **kwargs):
        if not session.get("usuario"):
            return redirect(url_for("login"))
        return vista(*args, **kwargs)

    return envoltorio


LOGIN_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mesa Millonaria - Login</title>
<style>
  body {{ background:#0f1115; color:#e7e9ee; font-family:-apple-system,sans-serif;
    display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
  form {{ background:#171a21; padding:28px; border-radius:14px; width:280px;
    box-shadow:0 4px 20px rgba(0,0,0,.4); }}
  h1 {{ font-size:18px; margin:0 0 18px; text-align:center; }}
  input {{ width:100%; padding:10px; margin-bottom:12px; border-radius:8px;
    border:1px solid #2a2f3a; background:#20242e; color:#e7e9ee; box-sizing:border-box; }}
  button {{ width:100%; padding:10px; border-radius:8px; border:none;
    background:#d97706; color:#1a1200; font-weight:700; cursor:pointer; }}
  .error {{ color:#f87171; font-size:13px; text-align:center; margin-bottom:10px; }}
</style></head>
<body>
<form method="POST">
  <h1>🎤 Mesa Millonaria</h1>
  {error}
  <input name="usuario" placeholder="Usuario" autofocus required>
  <input name="clave" type="password" placeholder="Contraseña" required>
  <button type="submit">Entrar</button>
</form>
</body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        clave = request.form.get("clave") or ""
        clave_real = USUARIOS.get(usuario)
        if clave_real is not None and hmac.compare_digest(clave_real, clave):
            session["usuario"] = usuario
            return redirect(url_for("index"))
        error = '<div class="error">Usuario o contraseña incorrectos</div>'
    return LOGIN_HTML.format(error=error)


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))


@app.route("/")
@requiere_login
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "chat.html")


@app.route("/api/archivo")
@requiere_login
def api_archivo():
    """Sirve para descargar un archivo real generado (CSV, HTML, PDF, etc.)
    - solo permite servir archivos que estén adentro de planes/, para no
    exponer el resto del disco."""
    ruta = request.args.get("ruta", "")
    base = os.path.abspath(debate.PLANES_DIR)
    ruta_absoluta = os.path.abspath(ruta)
    if not ruta_absoluta.startswith(base + os.sep) or not os.path.isfile(ruta_absoluta):
        abort(404)
    return send_file(ruta_absoluta, as_attachment=True)


@app.route("/api/estado")
@requiere_login
def api_estado():
    with _lock:
        estado = estado_actual()
        return jsonify(
            usuario=session["usuario"],
            mensajes=estado["mensajes"],
            cerrado=estado["cerrado"],
            archivo_plan=estado["archivo_plan"],
            tema=estado["tema"],
        )


@app.route("/api/nuevo", methods=["POST"])
@requiere_login
def api_nuevo():
    with _lock:
        _estados[session["usuario"]] = _estado_nuevo()
    return jsonify(ok=True)


@app.route("/api/mensaje", methods=["POST"])
@requiere_login
def api_mensaje():
    data = request.get_json(force=True) or {}
    texto = (data.get("texto") or "").strip()
    if not texto:
        return jsonify(error="Mensaje vacío"), 400
    with _lock:
        estado = estado_actual()
        if estado["tema"] is None:
            estado["tema"] = texto
            estado["historial"] = "Moderador: " + texto + "\n"
        else:
            estado["historial"] += "\nModerador: " + texto + "\n"
        estado["mensajes"].append({"autor": "Moderador", "texto": texto})
    return jsonify(ok=True)


@app.route("/api/siguiente", methods=["POST"])
@requiere_login
def api_siguiente():
    with _lock:
        estado = estado_actual()
        if estado["tema"] is None:
            return jsonify(error="Mandá un mensaje primero para arrancar"), 400
        if estado["cerrado"]:
            return jsonify(error="Este debate ya está cerrado, empezá uno nuevo"), 400
        # Orden aleatorio de quién habla, evitando que el mismo hable dos veces seguidas.
        ultimo_autor = estado["mensajes"][-1]["autor"] if estado["mensajes"] else None
        candidatos = [par for par in debate.AGENTES if par[0] != ultimo_autor]
        nombre, funcion = random.choice(candidatos or list(debate.AGENTES))
        historial = estado["historial"]

    try:
        texto = funcion(historial).strip()
    except Exception as e:
        return jsonify(error=f"{nombre} falló: {e}"), 502

    texto, listo = debate.extraer_listo(texto)

    with _lock:
        estado = estado_actual()
        estado["historial"] += f"\n{nombre}: {texto}\n"
        estado["turno"] += 1
        mensaje = {"autor": nombre, "texto": texto, "listo": listo}
        estado["mensajes"].append(mensaje)
    return jsonify(mensaje)


@app.route("/api/cerrar", methods=["POST"])
@requiere_login
def api_cerrar():
    with _lock:
        estado = estado_actual()
        if estado["tema"] is None:
            return jsonify(error="Todavía no hay nada que cerrar"), 400
        historial = estado["historial"]
        tema = estado["tema"]

    compromisos = debate.cerrar_acuerdo(historial, silencioso=True)
    if not compromisos:
        return jsonify(error="Ningún agente pudo cerrar el plan (falló la API)"), 502

    archivo = debate.guardar_plan(tema, compromisos)

    with _lock:
        estado = estado_actual()
        for nombre, texto in compromisos:
            estado["mensajes"].append({"autor": nombre, "texto": texto, "cierre": True})
        estado["cerrado"] = True
        estado["archivo_plan"] = archivo

    return jsonify(
        compromisos=[{"autor": n, "texto": t} for n, t in compromisos],
        archivo=archivo,
    )


@app.route("/api/orden", methods=["POST"])
@requiere_login
def api_orden():
    """Los tres le dan al usuario una orden de trabajo concreta para llevar
    a cabo la idea, sin cerrar el chat (se puede seguir charlando después)."""
    with _lock:
        estado = estado_actual()
        if estado["tema"] is None:
            return jsonify(error="Todavía no hay nada de qué armar una orden"), 400
        historial = estado["historial"]
        tema = estado["tema"]

    timestamp = time.strftime("%Y-%m-%d_%Hh%M")
    carpeta_archivos = os.path.join(
        debate.PLANES_DIR, f"orden_{session['usuario']}_{timestamp}_archivos"
    )
    instrucciones, archivos = debate.dar_orden_trabajo(
        historial, silencioso=True, carpeta_archivos=carpeta_archivos
    )
    if not instrucciones:
        return jsonify(error="Ningún agente pudo armar la orden de trabajo (falló la API)"), 502

    archivo = debate.guardar_orden(tema, instrucciones, timestamp=f"{session['usuario']}_{timestamp}")

    with _lock:
        estado = estado_actual()
        for nombre, texto in instrucciones:
            estado["mensajes"].append({"autor": nombre, "texto": texto, "orden": True})

    return jsonify(
        instrucciones=[{"autor": n, "texto": t} for n, t in instrucciones],
        archivo=archivo,
        archivos_generados=[{"nombre": os.path.basename(a), "ruta": a} for a in archivos],
    )


@app.route("/api/ejecutar", methods=["POST"])
@requiere_login
def api_ejecutar():
    with _lock:
        estado = estado_actual()
        archivo = estado["archivo_plan"]
    archivo = archivo or debate.encontrar_ultimo_plan()
    if not archivo:
        return jsonify(error="No hay ningún plan guardado todavía"), 400

    debate.ejecutar_plan(archivo)

    carpeta = os.path.splitext(archivo)[0] + "_ejecucion"
    resultado = {}
    nombres_txt = {f"{n.lower()}.txt" for n, _fn in debate.AGENTES} | {"todo_junto.txt"}
    for nombre, _fn in debate.AGENTES:
        ruta = os.path.join(carpeta, f"{nombre.lower()}.txt")
        if os.path.isfile(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                resultado[nombre] = f.read()

    # Cualquier otro archivo real generado (CSV, HTML, CSS, JS, PDF) que no
    # sea uno de los .txt de lectura de cada agente.
    archivos_generados = []
    if os.path.isdir(carpeta):
        for nombre_archivo in sorted(os.listdir(carpeta)):
            if nombre_archivo.lower() not in nombres_txt:
                archivos_generados.append({
                    "nombre": nombre_archivo,
                    "ruta": os.path.join(carpeta, nombre_archivo),
                })

    return jsonify(resultado=resultado, carpeta=carpeta, archivos_generados=archivos_generados)


if __name__ == "__main__":
    if not USUARIOS:
        print(
            "\n⚠️  No hay usuarios configurados (variable USUARIOS en el .env).\n"
            "   Nadie va a poder entrar. Ver LEEME.txt para configurarlos.\n"
        )
    puerto = int(os.getenv("PORT", "5050"))
    print("\n🎤 Mesa Millonaria - chat web")
    print(f"   En esta Mac:   http://localhost:{puerto}")
    print(f"   Desde el celu (misma wifi): http://<ip-de-tu-mac>:{puerto}\n")
    app.run(host="0.0.0.0", port=puerto, debug=False, threaded=True)
