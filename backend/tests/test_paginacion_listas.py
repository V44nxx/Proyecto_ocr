"""
Las listas se piden por páginas y no se cortan: Personas, fichas y diferencias.
Antes las pantallas pedían una sola página (300 personas, 100 fichas, 100 diferencias) y lo demás no se veía.
- Con muchos registros de la misma hora, recorrer las páginas trae a todos una sola vez (orden estable).
- Una página no puede pedir más de 1000 registros.
Datos inventados.
"""
from datetime import datetime, timezone

from tests.utilidades_pg import cabecera, crear_ficha, crear_persona, crear_usuario, requiere_postgres

MISMA_HORA = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)


def _recorrer(api, ruta, headers, tamano, **params):
    vistos, skip = [], 0
    while True:
        r = api.get(ruta, headers=headers, params={**params, "skip": skip, "limit": tamano})
        assert r.status_code == 200, r.text
        pagina = r.json()
        vistos += [x["id"] for x in pagina]
        if len(pagina) < tamano:
            return vistos
        skip += tamano


@requiere_postgres
def test_las_paginas_de_personas_traen_a_todos_una_vez(bd, api):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana)
    for i in range(250):
        crear_persona(db, ana, ficha, f"1000{i:06d}", "PRUEBA", f"LOTE {i:03d}", fecha_registro=MISMA_HORA)
    headers, id_ficha = cabecera(ana), str(ficha.id)
    db.close()

    vistos = _recorrer(api, "/api/personas", headers, 40, documento_id=id_ficha)
    assert len(vistos) == 250 and len(set(vistos)) == 250


@requiere_postgres
def test_las_paginas_de_fichas_traen_todas_una_vez(bd, api):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    for i in range(130):
        crear_ficha(db, ana, f"31{i:05d}.pdf", fecha_carga=MISMA_HORA)
    headers = cabecera(ana)
    db.close()

    vistos = _recorrer(api, "/api/documentos", headers, 50)
    assert len(vistos) == 130 and len(set(vistos)) == 130


@requiere_postgres
def test_las_paginas_de_diferencias_traen_todas(bd, api):
    from app.models.comparacion import Comparacion
    from app.models.diferencia import Diferencia
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    comp = Comparacion(usuario_id=ana.id, nombre_archivo="p.xlsx", nombre_original="p.xlsx", estado="completado")
    db.add(comp)
    db.commit()
    db.add_all([Diferencia(comparacion_id=comp.id, numero_identificacion=f"1000{i % 50:06d}", campo="nombres",
                           valor_bd="A", valor_excel="B", tipo_diferencia="diferente") for i in range(180)])
    db.commit()
    headers, id_comp = cabecera(ana), str(comp.id)
    db.close()

    vistos = _recorrer(api, f"/api/comparacion/{id_comp}/diferencias", headers, 70)
    assert len(vistos) == 180 and len(set(vistos)) == 180


@requiere_postgres
def test_una_pagina_no_pide_mas_de_mil(bd, api):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    headers = cabecera(ana)
    db.close()
    for ruta in ("/api/personas", "/api/documentos"):
        assert api.get(ruta, headers=headers, params={"limit": 1001}).status_code == 422
        assert api.get(ruta, headers=headers, params={"skip": -1}).status_code == 422
        assert api.get(ruta, headers=headers, params={"limit": 1000}).status_code == 200


@requiere_postgres
def test_las_paginas_del_historial_de_comparaciones_traen_todas(bd, api):
    from app.models.comparacion import Comparacion
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    db.add_all([Comparacion(usuario_id=ana.id, nombre_archivo=f"p{i}.xlsx", nombre_original=f"p{i}.xlsx",
                            estado="completado", fecha_carga=MISMA_HORA) for i in range(45)])
    db.commit()
    headers = cabecera(ana)
    db.close()

    vistos = _recorrer(api, "/api/comparacion", headers, 20)
    assert len(vistos) == 45 and len(set(vistos)) == 45
