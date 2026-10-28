"""Ficha escaneada inventada: cada persona ocupa dos páginas (frente y reverso de una cédula), como imagen y sin
texto en el PDF, así que pasa por el OCR. Nombres y números son combinaciones al azar, no de personas reales.

generar(ruta, personas, semilla) -> lista con lo que debería leerse de cada persona.
"""
import io
import random
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFilter, ImageFont

NOMBRES_F = ["LAURA", "MARIA", "DIANA", "PAULA", "ANDREA", "CAMILA", "SOFIA", "VALENTINA", "NATALIA", "CAROLINA"]
NOMBRES_M = ["JUAN", "CARLOS", "ANDRES", "FELIPE", "SANTIAGO", "MATEO", "DAVID", "SEBASTIAN", "CAMILO", "DANIEL"]
SEGUNDOS_F = ["MILENA", "ALEJANDRA", "FERNANDA", "LUCIA", "ISABEL", ""]
SEGUNDOS_M = ["ESTEBAN", "JOSE", "MANUEL", "ANDRES", "DAVID", ""]
APELLIDOS = ["GOMEZ", "RODRIGUEZ", "MARTINEZ", "GARCIA", "LOPEZ", "HERNANDEZ", "RAMIREZ", "TORRES", "MORENO",
             "JIMENEZ", "ROJAS", "VARGAS", "CASTRO", "ORTIZ", "SUAREZ", "MEDINA", "HERRERA", "AGUILAR"]
LUGARES = [("BUCARAMANGA", "SANTANDER"), ("MEDELLIN", "ANTIOQUIA"), ("CALI", "VALLE"), ("TUNJA", "BOYACA"),
           ("NEIVA", "HUILA"), ("PASTO", "NARIÑO"), ("IBAGUE", "TOLIMA"), ("MONTERIA", "CORDOBA")]
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
RH = ["O+", "A+", "B+", "O-", "AB+"]

FUENTES = {False: ("arial.ttf", "DejaVuSans.ttf"), True: ("arialbd.ttf", "DejaVuSans-Bold.ttf")}
ANCHO, ALTO = 2550, 3300            # carta a 300 DPI


def _persona(r):
    sexo = r.choice("FM")
    nombres = " ".join(x for x in (r.choice(NOMBRES_F if sexo == "F" else NOMBRES_M),
                                   r.choice(SEGUNDOS_F if sexo == "F" else SEGUNDOS_M)) if x)
    apellidos = f"{r.choice(APELLIDOS)} {r.choice(APELLIDOS)}"
    numero = str(r.randint(1_000_000_000, 1_099_999_999))
    anio, mes, dia = r.randint(1975, 2004), r.randint(1, 12), r.randint(1, 28)
    lugar, depto = r.choice(LUGARES)
    return {
        "numero_identificacion": numero, "nombres": nombres, "apellidos": apellidos, "sexo": sexo,
        "fecha_nacimiento": f"{anio:04d}-{mes:02d}-{dia:02d}",
        "_nacimiento": f"{dia:02d}-{MESES[mes - 1]}-{anio}", "_lugar": f"{lugar} ({depto})",
        "_expedicion": f"{dia:02d}-{MESES[(mes + 2) % 12]}-{anio + 18} {lugar}",
        "_estatura": f"1.{r.randint(50, 85)}", "_rh": r.choice(RH),
    }


def _fuente(negrita, tam):
    for nombre in FUENTES[negrita]:
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default(size=tam)


def _numero_con_puntos(n):
    return f"{int(n):,}".replace(",", ".")


def _tarjeta(lineas, r):
    """Una cara de la cédula dibujada en una hoja carta, levemente girada y con ruido, como una fotocopia."""
    hoja = Image.new("L", (ANCHO, ALTO), 250)
    tarjeta = Image.new("L", (1700, 1080), 238)
    d = ImageDraw.Draw(tarjeta)
    d.rounded_rectangle((4, 4, 1695, 1075), radius=40, outline=90, width=6)
    for texto, x, y, tam, negrita in lineas:
        d.text((x, y), texto, fill=25, font=_fuente(negrita, tam))
    tarjeta = tarjeta.rotate(r.uniform(-1.5, 1.5), expand=True, fillcolor=250)
    hoja.paste(tarjeta, (400 + r.randint(-40, 40), 500 + r.randint(-40, 40)))
    ruido = Image.effect_noise((ANCHO, ALTO), 14)
    hoja = Image.blend(hoja, ruido, 0.08).filter(ImageFilter.GaussianBlur(0.6))
    return hoja


def _frente(p, r):
    return _tarjeta([
        ("REPUBLICA DE COLOMBIA", 520, 60, 64, True),
        ("IDENTIFICACION PERSONAL", 560, 140, 48, False),
        ("CEDULA DE CIUDADANIA", 560, 200, 52, True),
        (f"NUMERO {_numero_con_puntos(p['numero_identificacion'])}", 560, 300, 64, True),
        (p["apellidos"], 560, 440, 60, True),
        ("APELLIDOS", 560, 510, 36, False),
        (p["nombres"], 560, 620, 60, True),
        ("NOMBRES", 560, 690, 36, False),
        ("FIRMA", 560, 900, 36, False),
    ], r)


def _reverso(p, r):
    return _tarjeta([
        ("FECHA DE NACIMIENTO", 80, 80, 40, False), (p["_nacimiento"], 80, 130, 56, True),
        ("LUGAR DE NACIMIENTO", 80, 230, 40, False), (p["_lugar"], 80, 280, 56, True),
        ("ESTATURA", 80, 390, 40, False), (p["_estatura"], 80, 440, 56, True),
        ("G.S. RH", 420, 390, 40, False), (p["_rh"], 420, 440, 56, True),
        ("SEXO", 700, 390, 40, False), (p["sexo"], 700, 440, 56, True),
        ("FECHA Y LUGAR DE EXPEDICION", 80, 560, 40, False), (p["_expedicion"], 80, 610, 56, True),
        ("INDICE DERECHO", 1250, 900, 36, False),
        ("REGISTRADOR NACIONAL", 80, 900, 36, False),
    ], r)


def generar(ruta, personas=6, semilla=27):
    r = random.Random(semilla)
    gente = [_persona(r) for _ in range(personas)]
    doc = fitz.open()
    for p in gente:
        for imagen in (_frente(p, r), _reverso(p, r)):
            buf = io.BytesIO()
            imagen.save(buf, format="JPEG", quality=85)
            pag = doc.new_page(width=612, height=792)
            pag.insert_image(pag.rect, stream=buf.getvalue())
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    doc.save(ruta)
    return gente


def texto_de_pagina(p, cara):
    """Lo que devolvería un OCR perfecto de esa cara (para simular Document AI)."""
    if cara == "frente":
        return "\n".join(["REPUBLICA DE COLOMBIA", "IDENTIFICACION PERSONAL", "CEDULA DE CIUDADANIA",
                          f"NUMERO {_numero_con_puntos(p['numero_identificacion'])}", p["apellidos"], "APELLIDOS",
                          p["nombres"], "NOMBRES", "FIRMA"])
    return "\n".join(["FECHA DE NACIMIENTO", p["_nacimiento"], "LUGAR DE NACIMIENTO", p["_lugar"],
                      "ESTATURA G.S. RH SEXO", f"{p['_estatura']} {p['_rh']} {p['sexo']}",
                      "FECHA Y LUGAR DE EXPEDICION", p["_expedicion"], "INDICE DERECHO", "REGISTRADOR NACIONAL"])
