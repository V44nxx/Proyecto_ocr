# language: es
Característica: Cada cuenta ve solo sus propios datos
  Como operadora de KondID
  Quiero que nadie de otra cuenta vea las fichas ni las personas que yo cargué
  Para proteger los datos personales de las personas registradas

  Antecedentes:
    Dado que la operadora "ana@example.com" tiene una ficha con la persona de cédula "1000000402"
    Y tiene una comparación con diferencias
    Y existe otro operador "beto@example.com"

  Escenario: Otro operador no descarga el reporte de diferencias de Ana
    Cuando "beto@example.com" pide el reporte de diferencias de Ana
    Entonces el sistema responde que no existe

  Escenario: Otro operador no ve la imagen del documento de Ana
    Cuando "beto@example.com" pide la página 1 de la ficha de Ana
    Entonces el sistema responde que no existe

  Escenario: Otro operador no encuentra a la persona de Ana por su cédula
    Cuando "beto@example.com" busca la cédula "1000000402"
    Entonces el sistema responde que no existe

  Escenario: Otro operador no puede editar a la persona de Ana
    Cuando "beto@example.com" intenta cambiar el nombre de la persona de Ana
    Entonces el sistema responde que no existe

  Escenario: Ana sí descarga su reporte y la descarga queda registrada
    Cuando "ana@example.com" pide el reporte de diferencias de Ana
    Entonces recibe un archivo de Excel
    Y la acción "exportacion_diferencias" queda en la auditoría
