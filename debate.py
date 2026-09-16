"""
Mesa redonda de tema libre: Grok, ChatGPT y Claude charlan sobre lo que vos
les plantees (no tiene por qué ser un negocio - puede ser cualquier tema),
cada uno con su propia personalidad.
Vos sos el moderador: después de CADA mensaje podés meterte con un comentario,
como en un chat grupal.

Uso:
    python debate.py            -> arranca el debate
    python debate.py --modelos  -> lista los modelos disponibles en cada API
"""
import json
import os
import random
import re
import sys
import time

ESTADO_PATH = ".estado_auto.json"

from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI

load_dotenv()

# Nombres de modelo: se pueden cambiar desde el .env sin tocar el código
MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-sonnet-5")
MODELO_CHATGPT = os.getenv("MODELO_CHATGPT", "gpt-5.1")
MODELO_GROK = os.getenv("MODELO_GROK", "grok-4")

claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
chatgpt = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
grok = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

REGLAS = (
    " Estás en una mesa de tres con personalidades bien distintas, charlando con un "
    "moderador humano presente sobre el tema que él les dé - puede ser un negocio, una "
    "decisión personal, una opinión, un debate de café, lo que sea. Adaptá tu rol al "
    "tema en cuestión, no fuerces que todo termine siendo sobre plata o negocios si el "
    "tema no va por ahí. Respondé en español rioplatense, tono natural y directo, "
    "máximo 3-4 oraciones. Construí sobre lo que dijo el último que habló: sumale algo "
    "nuevo, contradecilo con un argumento concreto, o profundizá un punto - no repitas "
    "lo mismo con otras palabras ni des vueltas en círculo. Si el tema tiene una "
    "conclusión o decisión posible, la mesa va llegando hacia ahí de a poco; si no la "
    "tiene (una opinión, un debate sin resolución única), igual el intercambio tiene "
    "que avanzar y no estancarse."
)

PERSONAS = {
    "Grok": "Sos Grok: la voz más audaz y provocadora de la mesa. Ante cualquier tema, "
            "tirás la postura o la idea más fuerte y menos obvia, con seguridad y algo "
            "de sarcasmo, y la vas afinando con lo que aportan los otros dos sin "
            "repetir siempre el mismo argumento." + REGLAS,
    "ChatGPT": "Sos ChatGPT: el que ordena y estructura la conversación. Agarrás lo que "
               "se dijo y lo convertís en algo más claro y concreto - un argumento "
               "mejor armado, una lista de puntos, un paso siguiente, una estructura - "
               "sin perder de vista el tema original ni inventar datos." + REGLAS,
    "Claude": "Sos Claude: el que cuestiona y pone a prueba lo que se dijo. Detectás el "
              "punto más débil, el supuesto sin probar o la exageración de lo que se "
              "propuso, y lo señalás con un argumento concreto o una alternativa, no "
              "con una objeción genérica. Si el argumento ya es sólido, lo reconocés "
              "sin drama y sumás tu parte." + REGLAS,
}

ICONOS = {"Grok": "👽", "ChatGPT": "🧠", "Claude": "🦉", "Moderador": "🎤"}

COLORES = {
    "Grok": "\033[92m",       # verde
    "ChatGPT": "\033[96m",    # cian
    "Claude": "\033[95m",     # magenta
    "Moderador": "\033[93m",  # amarillo
}
NEGRITA = "\033[1m"
RESET = "\033[0m"


def escribir(texto, delay=0.015):
    """Imprime como si lo estuvieran tipeando, para que se sienta un chat en vivo."""
    for letra in texto:
        print(letra, end="", flush=True)
        time.sleep(delay)
    print()


def hablar_claude(historial, max_tokens=600):
    r = claude.messages.create(
        model=MODELO_CLAUDE,
        max_tokens=max_tokens,
        system=PERSONAS["Claude"],
        thinking={"type": "disabled"},  # respuesta directa, sin gastar tiempo/tokens pensando
        messages=[{"role": "user", "content": historial + "\n\nTu turno, Claude."}],
    )
    for bloque in r.content:
        if bloque.type == "text":
            return bloque.text
    return ""


def hablar_chatgpt(historial, max_tokens=600):
    r = chatgpt.chat.completions.create(
        model=MODELO_CHATGPT,
        max_completion_tokens=max_tokens,
        messages=[
            {"role": "system", "content": PERSONAS["ChatGPT"]},
            {"role": "user", "content": historial + "\n\nTu turno, ChatGPT."},
        ],
    )
    return r.choices[0].message.content


def hablar_grok(historial, max_tokens=600):
    r = grok.chat.completions.create(
        model=MODELO_GROK,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": PERSONAS["Grok"]},
            {"role": "user", "content": historial + "\n\nTu turno, Grok."},
        ],
    )
    return r.choices[0].message.content


AGENTES = [("Grok", hablar_grok), ("ChatGPT", hablar_chatgpt), ("Claude", hablar_claude)]


def orden_al_azar():
    """Devuelve a los 3 agentes en un orden mezclado, para que no hablen
    siempre Grok -> ChatGPT -> Claude en el mismo orden."""
    return random.sample(AGENTES, len(AGENTES))


def listar_modelos():
    print("\n--- Claude ---")
    try:
        for m in claude.models.list():
            print(" ", m.id)
    except Exception as e:
        print("  Error:", e)
    print("\n--- ChatGPT ---")
    try:
        for m in chatgpt.models.list():
            print(" ", m.id)
    except Exception as e:
        print("  Error:", e)
    print("\n--- Grok ---")
    try:
        for m in grok.models.list():
            print(" ", m.id)
    except Exception as e:
        print("  Error:", e)


PEDIDO_CIERRE = (
    "\n\nLa charla terminó. Ahora cada uno por separado, sin repetir el resumen de lo "
    "ya dicho: primero UNA oración con tu conclusión final sobre el tema (tu postura, "
    "lo que te convenció o no, o cómo quedaría resuelto). Después, SOLO SI el tema lo "
    "amerita (por ejemplo, si se armó algo con pasos a seguir), tu propia lista "
    "numerada de 3 a 5 puntos concretos que vos aportarías para llevarlo a la "
    "práctica, en orden. Si el tema no tiene una parte accionable (una opinión, un "
    "debate sin resolución única), con la oración de conclusión alcanza, no inventes "
    "tareas de la nada."
)


def cerrar_acuerdo(historial, silencioso=False):
    """Última pasada: cada uno confirma el plan y su compromiso concreto.
    Con silencioso=True no imprime ni tipea nada (para usar desde otra interfaz,
    como el chat web)."""
    if not silencioso:
        print(f"\n{NEGRITA}" + "=" * 15 + " ACUERDO FINAL " + "=" * 15 + RESET)
    compromisos = []
    for nombre, funcion in orden_al_azar():
        color = COLORES[nombre]
        if not silencioso:
            print(f"\n{color}{ICONOS[nombre]} {nombre} está escribiendo...{RESET}", end="", flush=True)
        try:
            texto = funcion(historial + PEDIDO_CIERRE).strip()
        except Exception as e:
            if not silencioso:
                print(f"\r{color}⚠️  {nombre} falló: {e}{RESET}" + " " * 20)
            continue
        if not silencioso:
            print("\r" + " " * 60 + "\r", end="")
            print(f"{color}{NEGRITA}{ICONOS[nombre]} {nombre}:{RESET} ", end="")
            escribir(f"{color}{texto}{RESET}")
        compromisos.append((nombre, texto))
        historial += "\n" + nombre + ": " + texto + "\n"
        if not silencioso:
            time.sleep(1.5)
    return compromisos


PLANES_DIR = "planes"

# Los modelos solo devuelven texto plano - no pueden generar un .xlsx, un
# sitio web o un PDF reales por su cuenta. Estos dos marcadores les permiten
# entregar archivos de verdad: piden el bloque en el formato exacto y acá lo
# convertimos en un archivo real en disco.
#
# ===ARCHIVO: nombre.ext===...===FIN===  -> cualquier archivo de texto tal
#   cual (CSV para planillas, HTML/CSS/JS para una página web real, JSON,
#   MD, TXT, lo que sea). Se guarda byte a byte como lo escribió el modelo.
#
# ===PDF: nombre.pdf===...===FIN===  -> el modelo escribe el contenido en
#   texto simple con algo de formato (# título, ## subtítulo, - viñeta) y acá
#   lo convertimos a un PDF real con fpdf2, porque un PDF es un formato
#   binario que el modelo no puede escribir directamente.
PATRON_ARCHIVO = re.compile(
    r"===\s*ARCHIVO\s*:\s*(?P<nombre>[^\n=]+?)\s*===\s*\n(?P<contenido>.*?)\n===\s*FIN\s*===",
    re.DOTALL | re.IGNORECASE,
)
PATRON_PDF = re.compile(
    r"===\s*PDF\s*:\s*(?P<nombre>[^\n=]+?)\s*===\s*\n(?P<contenido>.*?)\n===\s*FIN\s*===",
    re.DOTALL | re.IGNORECASE,
)

INSTRUCCION_ARCHIVOS = (
    "\n\nSi alguno de tus puntos da para ser un archivo real en vez de texto suelto, "
    "generalo de verdad en vez de describirlo, usando estos formatos EXACTOS (podés "
    "combinar varios bloques, uno por archivo):\n\n"
    "- Planilla, tabla o calendario (CSV real, con encabezados y filas con datos "
    "concretos, no vacíos):\n"
    "===ARCHIVO: nombre-del-archivo.csv===\n"
    "encabezado1,encabezado2,encabezado3\n"
    "valor1,valor2,valor3\n"
    "===FIN===\n\n"
    "- Página o sitio web: UN SOLO archivo HTML autocontenido (el CSS adentro de "
    "una etiqueta <style> y el JS adentro de <script>, todo en el mismo archivo, "
    "NO en archivos separados), real y funcional, listo para abrir en un navegador "
    "tal cual:\n"
    "===ARCHIVO: index.html===\n"
    "<!DOCTYPE html><html>...<style>...</style>...<script>...</script></html>\n"
    "===FIN===\n\n"
    "- Documento tipo PDF (propuesta, presentación de una página, plan escrito) - "
    "escribí el contenido en texto simple con # para título, ## para subtítulo y - "
    "para viñetas, así queda un documento prolijo:\n"
    "===PDF: nombre-del-documento.pdf===\n"
    "# Título\n"
    "## Subtítulo\n"
    "Texto del párrafo.\n"
    "- Punto uno\n"
    "- Punto dos\n"
    "===FIN===\n\n"
    "No inventes archivos que no hacen falta: usalos solo cuando el punto realmente "
    "sea una planilla, una web o un documento, no para todo."
)


def _texto_a_pdf(ruta, contenido):
    """Convierte texto simple (# título, ## subtítulo, - viñeta, párrafos) en
    un PDF real, usando fpdf2."""
    from fpdf import FPDF

    # La fuente por default de fpdf2 solo soporta Latin-1: reemplazamos los
    # caracteres típicos que rompen la generación (viñetas, comillas
    # tipográficas, rayas largas, emojis) por equivalentes simples.
    equivalencias = {
        "•": "-", "◦": "-", "●": "-",
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "—": "-", "–": "-", "…": "...",
    }
    for original, reemplazo in equivalencias.items():
        contenido = contenido.replace(original, reemplazo)
    contenido = contenido.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    for linea in contenido.split("\n"):
        linea = linea.strip()
        if not linea:
            pdf.ln(4)
        elif linea.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 10, linea[2:])
        elif linea.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, linea[3:])
        elif linea.startswith("- "):
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, "  -  " + linea[2:])
        else:
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, linea)
        # multi_cell no vuelve el cursor al margen izquierdo por su cuenta
        # (queda pegado a la derecha), así que lo reseteamos a mano o la
        # siguiente línea se queda sin ancho disponible y explota.
        pdf.set_x(pdf.l_margin)
    pdf.output(ruta)


def extraer_archivos(texto, carpeta_salida):
    """Busca bloques ===ARCHIVO:...=== y ===PDF:...=== en el texto de un
    agente, genera los archivos reales en disco, y devuelve el texto con
    esos bloques reemplazados por una nota corta (para no repetir contenido
    largo en el .txt de lectura)."""
    archivos_generados = []

    def nombre_seguro(bruto, extension_default):
        nombre = bruto.strip()
        if "." not in nombre:
            nombre += extension_default
        return re.sub(r"[^A-Za-z0-9_.-]", "_", nombre)

    def reemplazar_archivo(m):
        nombre = nombre_seguro(m.group("nombre"), ".txt")
        os.makedirs(carpeta_salida, exist_ok=True)
        ruta = os.path.join(carpeta_salida, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(m.group("contenido").strip() + "\n")
        archivos_generados.append(ruta)
        return f"[📄 Archivo generado: {nombre}]"

    def reemplazar_pdf(m):
        nombre = nombre_seguro(m.group("nombre"), ".pdf")
        if not nombre.lower().endswith(".pdf"):
            nombre += ".pdf"
        os.makedirs(carpeta_salida, exist_ok=True)
        ruta = os.path.join(carpeta_salida, nombre)
        try:
            _texto_a_pdf(ruta, m.group("contenido").strip())
            archivos_generados.append(ruta)
            return f"[📕 PDF generado: {nombre}]"
        except Exception as e:
            return f"[⚠️ No se pudo generar el PDF {nombre}: {e}]"

    texto_limpio = PATRON_ARCHIVO.sub(reemplazar_archivo, texto)
    texto_limpio = PATRON_PDF.sub(reemplazar_pdf, texto_limpio)
    return texto_limpio, archivos_generados


def guardar_plan(tema, compromisos):
    os.makedirs(PLANES_DIR, exist_ok=True)
    nombre_archivo = os.path.join(PLANES_DIR, f"plan_{time.strftime('%Y-%m-%d_%Hh%M')}.txt")
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write("CIERRE - Mesa Millonaria\n")
        f.write("Tema: " + tema + "\n")
        f.write("Fecha: " + time.strftime("%Y-%m-%d %H:%M") + "\n\n")
        for nombre, texto in compromisos:
            f.write(nombre + ": " + texto + "\n\n")
    print(f"\n{NEGRITA}📝 Cierre guardado en {nombre_archivo}{RESET}")
    return nombre_archivo


def encontrar_ultimo_plan():
    if not os.path.isdir(PLANES_DIR):
        return None
    archivos = sorted(
        f for f in os.listdir(PLANES_DIR) if f.startswith("plan_") and f.endswith(".txt")
    )
    return os.path.join(PLANES_DIR, archivos[-1]) if archivos else None


def ejecutar_plan(ruta_plan=None):
    """Hace que los tres agentes ESCRIBAN de verdad el contenido de los puntos
    accionables que salieron del cierre (textos, guiones, estructuras, lo que
    corresponda), en cadena: cada uno ve lo que escribió el anterior, para que
    todo quede coherente entre sí. Solo tiene sentido si el cierre incluyó
    puntos concretos, no una simple opinión."""
    ruta_plan = ruta_plan or encontrar_ultimo_plan()
    if not ruta_plan or not os.path.isfile(ruta_plan):
        print(f"No encontré ningún cierre guardado en {PLANES_DIR}/. Corré el chat "
              f"primero ('python debate.py') y cerralo para generar uno.")
        return

    with open(ruta_plan, "r", encoding="utf-8") as f:
        plan_texto = f.read()

    carpeta_salida = os.path.splitext(ruta_plan)[0] + "_ejecucion"
    os.makedirs(carpeta_salida, exist_ok=True)

    print(f"\n{NEGRITA}Desarrollando: {ruta_plan}{RESET}")
    print(f"El contenido real va a quedar en: {carpeta_salida}/\n")

    contexto_base = f"Esta es la charla ya cerrada, con la conclusión de cada uno:\n\n{plan_texto}"
    instruccion = (
        "\n\nNo describas qué harías ni resumas de nuevo la charla: ESCRIBÍ EL CONTENIDO "
        "REAL Y COMPLETO de los puntos concretos que vos (y solo vos) propusiste en tu "
        "conclusión, listo para copiar y usar directo. Separá cada punto con un título "
        "'## Punto N: <nombre corto>'. Nada de placeholders tipo '[poné acá tu texto]' ni "
        "de 'esto dependería de...': completá todo con contenido específico y creíble "
        "para este tema en particular. Si en tu conclusión no dejaste puntos accionables "
        "(por ejemplo, si el tema era solo una opinión), decilo en una frase y no "
        "inventes tareas de la nada."
        + INSTRUCCION_ARCHIVOS
    )

    salidas = []  # lista de (nombre, texto) en orden, para dar contexto al siguiente
    archivos_generados = []
    for nombre, funcion in orden_al_azar():
        color = COLORES[nombre]
        print(f"{color}{ICONOS[nombre]} {nombre} está escribiendo su parte...{RESET}",
              end="", flush=True)
        contexto_previos = "\n\n".join(
            f"Contenido que ya escribió {n}:\n{t}" for n, t in salidas
        )
        pedido = contexto_base + ("\n\n" + contexto_previos if contexto_previos else "") + instruccion
        try:
            texto = funcion(pedido, max_tokens=2500).strip()
        except Exception as e:
            print(f"\r{color}⚠️  {nombre} falló: {e}{RESET}" + " " * 20)
            continue
        print("\r" + " " * 60 + "\r", end="")
        texto, nuevos_archivos = extraer_archivos(texto, carpeta_salida)
        archivos_generados += nuevos_archivos
        ruta_archivo = os.path.join(carpeta_salida, f"{nombre.lower()}.txt")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(texto)
        salidas.append((nombre, texto))
        print(f"{color}{NEGRITA}✅ {nombre}{RESET} -> {ruta_archivo}")
        for ruta_gen in nuevos_archivos:
            print(f"   {NEGRITA}📁 {ruta_gen}{RESET}")

    if salidas:
        ruta_todo = os.path.join(carpeta_salida, "TODO_JUNTO.txt")
        with open(ruta_todo, "w", encoding="utf-8") as f:
            f.write(f"CONTENIDO EJECUTADO - {os.path.basename(ruta_plan)}\n")
            f.write("=" * 60 + "\n\n")
            for nombre, texto in salidas:
                f.write(f"########## {nombre} ##########\n\n{texto}\n\n\n")
        print(f"\n{NEGRITA}📦 Todo junto en: {ruta_todo}{RESET}\n")


PEDIDO_ORDEN = (
    "\n\nBasta de seguir debatiendo: al moderador humano le gustó por dónde va esto y "
    "ahora es momento de actuar. Ustedes tres son el equipo de estrategia; el moderador "
    "es su empleado humano, el único que puede hacer cosas en el mundo real (crear una "
    "cuenta, hablar con alguien, comprar algo, publicar, pagar, lo que haga falta) - "
    "ustedes no pueden hacer nada de eso, PERO sí pueden dejarle todo el trabajo digital "
    "ya armado (la web escrita, la planilla, el documento) para que él solo tenga que "
    "publicarlo o usarlo. Cada uno, en cadena (mirá lo que ya escribieron los anteriores "
    "para no pisarse ni repetirse), dale una orden de trabajo clara y en segunda persona "
    "('vos andá y...', 'conseguite...', 'escribile a...', 'subí este archivo a...'), con "
    "pasos concretos y en el orden en que los tiene que hacer, para la parte que le "
    "corresponde a tu rol en esta idea puntual. Nada de placeholders ni de 'investigá el "
    "mercado': cada paso tiene que ser una acción física o digital concreta y verificable "
    "(se puede tildar como hecha o no hecha)."
    + INSTRUCCION_ARCHIVOS
)


def dar_orden_trabajo(historial, silencioso=False, carpeta_archivos=None):
    """Los tres, en cadena, le dan al moderador humano una orden de trabajo
    concreta para llevar a cabo la idea que se estuvo charlando - tratándolo
    como su empleado, ya que ellos no pueden ejecutar nada en el mundo real.
    Si generan archivos reales (planillas, web, PDF), quedan en carpeta_archivos."""
    if not silencioso:
        print(f"\n{NEGRITA}" + "=" * 15 + " ORDEN DE TRABAJO " + "=" * 15 + RESET)
    instrucciones = []
    archivos_generados = []
    for nombre, funcion in orden_al_azar():
        color = COLORES[nombre]
        if not silencioso:
            print(f"\n{color}{ICONOS[nombre]} {nombre} está escribiendo...{RESET}", end="", flush=True)
        contexto_previo = "\n\n".join(
            f"Orden que ya dio {n}:\n{t}" for n, t in instrucciones
        )
        pedido = historial + ("\n\n" + contexto_previo if contexto_previo else "") + PEDIDO_ORDEN
        try:
            texto = funcion(pedido, max_tokens=1800).strip()
        except Exception as e:
            if not silencioso:
                print(f"\r{color}⚠️  {nombre} falló: {e}{RESET}" + " " * 20)
            continue
        if carpeta_archivos:
            texto, nuevos = extraer_archivos(texto, carpeta_archivos)
            archivos_generados += nuevos
        if not silencioso:
            print("\r" + " " * 60 + "\r", end="")
            print(f"{color}{NEGRITA}{ICONOS[nombre]} {nombre}:{RESET} ", end="")
            escribir(f"{color}{texto}{RESET}")
            for ruta_gen in nuevos if carpeta_archivos else []:
                print(f"   {NEGRITA}📁 {ruta_gen}{RESET}")
        instrucciones.append((nombre, texto))
    return instrucciones, archivos_generados


def guardar_orden(tema, instrucciones, timestamp=None):
    os.makedirs(PLANES_DIR, exist_ok=True)
    timestamp = timestamp or time.strftime("%Y-%m-%d_%Hh%M")
    nombre_archivo = os.path.join(PLANES_DIR, f"orden_{timestamp}.txt")
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write("ORDEN DE TRABAJO - Mesa Millonaria\n")
        f.write("Tema: " + tema + "\n")
        f.write("Fecha: " + time.strftime("%Y-%m-%d %H:%M") + "\n\n")
        for nombre, texto in instrucciones:
            f.write(nombre + ": " + texto + "\n\n")
    print(f"\n{NEGRITA}🫡 Orden de trabajo guardada en {nombre_archivo}{RESET}")
    return nombre_archivo


DEFAULT_TEMA = (
    "Che, denme su opinión sincera: ¿la inteligencia artificial va a crear "
    "más trabajos de los que destruye, o va a ser al revés? Y si tuvieran "
    "que apostar, ¿en qué se van a diferenciar los que les vaya bien de los "
    "que no?"
)


def cargar_estado():
    with open(ESTADO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(estado):
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def auto_nuevo(tema):
    """Arranca un debate en modo automático (controlado por comandos, sin input()).
    Guarda el estado en disco para que --auto-ronda lo siga ronda por ronda."""
    tema = tema or DEFAULT_TEMA
    estado = {"tema": tema, "historial": "Moderador: " + tema + "\n", "ronda": 0}
    guardar_estado(estado)
    print(f"\n{COLORES['Moderador']}{NEGRITA}🎤 TEMA: {tema}{RESET}")
    print("Estado creado. Corré 'python debate.py --auto-ronda' para la ronda 1.")


def auto_ronda():
    """Corre UNA ronda más desde el estado guardado (sin efecto de tipeo, para ir rápido)."""
    estado = cargar_estado()
    estado["ronda"] += 1
    historial = estado["historial"]
    print(f"\n{NEGRITA}" + "=" * 20 + " RONDA " + str(estado["ronda"]) + " " + "=" * 20 + RESET)
    for nombre, funcion in orden_al_azar():
        color = COLORES[nombre]
        try:
            texto = funcion(historial).strip()
        except Exception as e:
            print(f"{color}⚠️  {nombre} falló: {e}{RESET}")
            continue
        print(f"{color}{NEGRITA}{ICONOS[nombre]} {nombre}:{RESET} {color}{texto}{RESET}")
        historial += "\n" + nombre + ": " + texto + "\n"
    estado["historial"] = historial
    guardar_estado(estado)
    print(f"\n(Si ya te convenció la charla: 'python debate.py --auto-cerrar'. "
          f"Si no: 'python debate.py --auto-ronda' de nuevo.)")


def auto_cerrar():
    """Cierra el debate en modo automático: pide compromisos y guarda PLAN_FINAL.txt."""
    estado = cargar_estado()
    compromisos = cerrar_acuerdo(estado["historial"])
    if compromisos:
        guardar_plan(estado["tema"], compromisos)
    os.remove(ESTADO_PATH)
    print(f"\n{NEGRITA}--- FIN DEL DEBATE (modo auto) ---{RESET}\n")


def auto_orden():
    """Pide la orden de trabajo sin cerrar el chat (podés seguir charlando después)."""
    estado = cargar_estado()
    timestamp = time.strftime("%Y-%m-%d_%Hh%M")
    carpeta_archivos = os.path.join(PLANES_DIR, f"orden_{timestamp}_archivos")
    instrucciones, archivos = dar_orden_trabajo(estado["historial"], carpeta_archivos=carpeta_archivos)
    if instrucciones:
        guardar_orden(estado["tema"], instrucciones, timestamp=timestamp)
    if archivos:
        print(f"{NEGRITA}📁 Archivos reales generados en: {carpeta_archivos}/{RESET}")


def debate(tema, rondas=30):
    historial = "Moderador: " + tema + "\n"
    print(f"\n{COLORES['Moderador']}{NEGRITA}🎤 TEMA: {tema}{RESET}")

    prompt_moderador = (
        f"{COLORES['Moderador']}🎤 (Enter sigue, escribí para meterte, "
        f"'salir' corta): {RESET}"
    )
    cortado = False

    for ronda in range(1, rondas + 1):
        if cortado:
            break
        print(f"\n{NEGRITA}" + "=" * 20 + " RONDA " + str(ronda) + " " + "=" * 20 + RESET)
        for nombre, funcion in orden_al_azar():
            color = COLORES[nombre]
            print(f"\n{color}{ICONOS[nombre]} {nombre} está escribiendo...{RESET}", end="", flush=True)
            try:
                texto = funcion(historial).strip()
            except Exception as e:
                print(f"\r{color}⚠️  {nombre} falló: {e}{RESET}" + " " * 20)
                continue  # si uno falla, el debate sigue con los otros
            print("\r" + " " * 60 + "\r", end="")  # borra el "está escribiendo..."
            print(f"{color}{NEGRITA}{ICONOS[nombre]} {nombre}:{RESET} ", end="")
            escribir(f"{color}{texto}{RESET}")
            historial += "\n" + nombre + ": " + texto + "\n"

            extra = input(f"\n{prompt_moderador}").strip()
            if extra.lower() == "salir":
                cortado = True
                break
            if extra:
                historial += "\nModerador: " + extra + "\n"
                print(f"{COLORES['Moderador']}{NEGRITA}🎤 Moderador:{RESET} {COLORES['Moderador']}{extra}{RESET}")

    compromisos = cerrar_acuerdo(historial)
    if compromisos:
        guardar_plan(tema, compromisos)

    print(f"\n{NEGRITA}--- FIN DEL DEBATE ---{RESET}\n")


if __name__ == "__main__":
    if "--modelos" in sys.argv:
        listar_modelos()
    elif "--auto-nuevo" in sys.argv:
        idx = sys.argv.index("--auto-nuevo")
        tema_cli = " ".join(sys.argv[idx + 1:]).strip()
        auto_nuevo(tema_cli)
    elif "--auto-ronda" in sys.argv:
        auto_ronda()
    elif "--auto-cerrar" in sys.argv:
        auto_cerrar()
    elif "--auto-orden" in sys.argv:
        auto_orden()
    elif "--ejecutar" in sys.argv:
        idx = sys.argv.index("--ejecutar")
        ruta_cli = " ".join(sys.argv[idx + 1:]).strip()
        ejecutar_plan(ruta_cli or None)
    else:
        tema = input("🎤 Tema del debate (Enter para el default): ").strip()
        if not tema:
            tema = DEFAULT_TEMA
        debate(tema)
