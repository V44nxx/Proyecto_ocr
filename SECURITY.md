# Política de seguridad

KondID procesa documentos de identidad de personas reales, incluidos menores de edad. Si encuentras una falla de
seguridad, gracias por avisarnos: así la corregimos antes de que alguien la aproveche.

## Versión con soporte

Solo la versión que está en producción, que es la última publicada en el [CHANGELOG](CHANGELOG.md). Las correcciones
de seguridad no se aplican a versiones anteriores.

## Cómo reportar una falla

**No abras un issue ni un pull request público** describiendo la falla: el repositorio es público y cualquiera podría
aprovecharla antes de que esté corregida.

1. En la pestaña **Security** del repositorio, usa **Report a vulnerability**, si está disponible. El reporte queda
   privado entre tú y los mantenedores.
2. Si esa opción no aparece, escribe en privado en GitHub a los mantenedores (V44nxx o Manuel151025) y pide un medio
   privado para enviar los detalles.

Incluye:

- qué parte del sistema está afectada (pantalla, ruta de la API o archivo);
- qué podría hacer alguien con la falla;
- cómo la encontraste, con los pasos mínimos para reproducirla en un entorno de prueba.

## Qué no hacer

- No pruebes contra producción (`proyectoocr.v44nxx.online` y `api.v44nxx.online`). Usa una instalación local con
  datos inventados (ver [docs/PRUEBAS.md](docs/PRUEBAS.md)).
- No abras, copies ni guardes datos de otras personas o de otras cuentas, aunque la falla lo permita.
- No hagas pruebas de carga o de negación de servicio.
- No incluyas datos personales reales en el reporte.

## Qué pasa después

- Confirmamos que recibimos el reporte y lo revisamos lo antes posible.
- Si la falla se confirma, se corrige en una versión nueva. El CHANGELOG la menciona sin detalles que sirvan para
  aprovecharla en instalaciones sin actualizar.
- Si quieres, te damos el crédito en esa versión.
