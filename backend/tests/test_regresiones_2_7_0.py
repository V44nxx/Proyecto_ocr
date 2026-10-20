"""
Regresiones corregidas en la versión 2.7.0 (encontradas en las pruebas de carga).
"""
from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia
from tests.utilidades_pg import cabecera, crear_ficha, crear_persona, crear_usuario, requiere_postgres


@requiere_postgres
def test_listar_personas_con_comparacion_sin_archivo_no_falla_la_autocorreccion(bd, api, monkeypatch):
    """
    Una comparación vieja cuya planilla ya no está en disco ni en la base deja la autocorrección sin planilla:
    debe saltarse en silencio, no fallar en cada consulta de la lista de personas.
    """
    import app.routers.personas as rutas_personas
    avisos = []
    monkeypatch.setattr(rutas_personas.logger, "warning", lambda mensaje, *a, **k: avisos.append(str(mensaje)))

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana)
    crear_persona(db, ana, ficha, "1000000999", "LUIS", "PEREZ")
    comp = Comparacion(usuario_id=ana.id, nombre_archivo="vieja.xlsx", nombre_original="vieja.xlsx", estado="completado")
    db.add(comp)
    db.commit()
    db.add(Diferencia(comparacion_id=comp.id, numero_identificacion="1000000402", campo="nombres",
                      valor_bd="A", valor_excel="B", tipo_diferencia="diferente"))
    db.commit()

    r = api.get("/api/personas", headers=cabecera(ana))
    db.close()

    assert r.status_code == 200
    assert not [a for a in avisos if "auto-corrección" in a], avisos
