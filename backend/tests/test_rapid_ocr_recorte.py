"""
RapidOCR lee solo la parte de la hoja que tiene algo impreso. Antes se achicaba la hoja entera a 1250 px y la
cédula, que ocupa una parte, quedaba tan pequeña que las palabras en negrita se pegaban («SANTIAGOMANUEL»).
Con imágenes inventadas.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.rapid_ocr_service import RapidOCRService, rapid_ocr_service

ANCHO, ALTO = 2550, 3300            # hoja carta a 300 DPI


def _hoja_con_tarjeta(lineas, origen=(400, 500)):
    hoja = Image.new("RGB", (ANCHO, ALTO), (250, 250, 250))
    d = ImageDraw.Draw(hoja)
    x0, y0 = origen
    d.rounded_rectangle((x0, y0, x0 + 1700, y0 + 1080), radius=40, outline=(90, 90, 90), width=6)
    for texto, x, y, tam in lineas:
        try:
            fuente = ImageFont.truetype("arialbd.ttf", tam)
        except OSError:
            try:
                fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", tam)        # Linux (CI)
            except OSError:
                fuente = ImageFont.load_default(size=tam)
        d.text((x0 + x, y0 + y), texto, fill=(25, 25, 25), font=fuente)
    return np.array(hoja)[:, :, ::-1].copy()


def test_zona_con_contenido_deja_fuera_la_hoja_en_blanco():
    img = _hoja_con_tarjeta([("REPUBLICA DE COLOMBIA", 520, 60, 64)])
    x0, y0, x1, y1 = RapidOCRService.zona_con_contenido(img)
    assert x0 <= 400 and y0 <= 500 and x1 >= 2100 and y1 >= 1580           # la tarjeta entera queda adentro
    assert (x1 - x0) * (y1 - y0) < 0.4 * ANCHO * ALTO                       # y casi toda la hoja en blanco, afuera


def test_hoja_llena_o_en_blanco_no_se_recorta():
    ruido = np.random.default_rng(7).integers(0, 255, (ALTO, ANCHO, 3), dtype=np.uint8)
    assert RapidOCRService.zona_con_contenido(ruido) is None
    assert RapidOCRService.zona_con_contenido(np.full((ALTO, ANCHO, 3), 250, dtype=np.uint8)) is None


def test_el_motor_recibe_solo_la_tarjeta_y_las_coordenadas_son_de_la_hoja(monkeypatch):
    img = _hoja_con_tarjeta([("SANTIAGO MANUEL", 560, 620, 60)])
    recibido = {}

    def motor(img_proc):
        recibido["forma"] = img_proc.shape
        alto, ancho = img_proc.shape[:2]
        # Una línea de texto justo en el centro de lo que recibe el motor
        caja = [[ancho * 0.4, alto * 0.45], [ancho * 0.6, alto * 0.45], [ancho * 0.6, alto * 0.55], [ancho * 0.4, alto * 0.55]]
        return [[caja, "SANTIAGO MANUEL", 0.99]], [0.1]

    monkeypatch.setattr(rapid_ocr_service, "_engine", motor)
    monkeypatch.setattr(rapid_ocr_service, "_disponible", True)
    texto, _, resultado = rapid_ocr_service.procesar_imagen(img, pagina_num=1)

    x0, y0, x1, y1 = RapidOCRService.zona_con_contenido(img)
    alto_rec, ancho_rec = recibido["forma"][:2]
    assert max(alto_rec, ancho_rec) <= 1250
    assert abs(ancho_rec / alto_rec - (x1 - x0) / (y1 - y0)) < 0.01        # recibió el recorte, no la hoja entera
    linea = resultado.pages[0].lines[0]
    assert abs(linea.x - (x0 + 0.4 * (x1 - x0)) / ANCHO) < 0.003            # y la línea vuelve a su sitio en la hoja
    assert abs(linea.y - (y0 + 0.45 * (y1 - y0)) / ALTO) < 0.003
    assert abs(linea.w - 0.2 * (x1 - x0) / ANCHO) < 0.003


def test_rapidocr_entrega_separados_los_nombres_conocidos_que_lee_pegados(monkeypatch):
    lineas = ["REPUBLICADECOLOMBIA", "NUMERO1.021.069.433", "GOMEZVARGAS", "APELLIDOS", "SEBASTIANMANUEL",
              "NOMBRES", "LUGARDENACIMIENTO", "VILLAVICENCIO (META)"]

    def motor(img_proc):
        return [[[[0, i * 10], [100, i * 10], [100, i * 10 + 8], [0, i * 10 + 8]], texto, 0.99]
                for i, texto in enumerate(lineas)], [0.1]

    monkeypatch.setattr(rapid_ocr_service, "_engine", motor)
    monkeypatch.setattr(rapid_ocr_service, "_disponible", True)
    texto, _, resultado = rapid_ocr_service.procesar_imagen(np.full((400, 300, 3), 250, dtype=np.uint8), pagina_num=1)

    assert texto.split("\n") == ["REPUBLICADECOLOMBIA", "NUMERO1.021.069.433", "GOMEZ VARGAS", "APELLIDOS",
                                 "SEBASTIAN MANUEL", "NOMBRES", "LUGARDENACIMIENTO", "VILLAVICENCIO (META)"]
    assert [t.text for t in resultado.pages[0].lines[4].tokens] == ["SEBASTIAN", "MANUEL"]
