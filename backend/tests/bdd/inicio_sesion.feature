# language: es
Característica: Inicio de sesión
  Como operador de KondID
  Quiero entrar con mi correo y mi contraseña
  Para trabajar con las fichas de mi cuenta sin que nadie pueda adivinar mi contraseña

  Antecedentes:
    Dado que existe el usuario "beto@example.com" con la contraseña "ClaveBeto-2026"

  Escenario: Entra con sus credenciales correctas
    Cuando inicia sesión con "beto@example.com" y "ClaveBeto-2026"
    Entonces entra al sistema
    Y la acción "login_exitoso" queda en la auditoría

  Escenario: Una contraseña equivocada no entra
    Cuando inicia sesión con "beto@example.com" y "equivocada"
    Entonces el sistema responde "Credenciales incorrectas"
    Y la acción "login_fallido" queda en la auditoría

  Escenario: Tras 5 intentos fallidos hay que esperar, aunque después escriba la contraseña correcta
    Dado que alguien intentó entrar 5 veces a "beto@example.com" con contraseñas equivocadas
    Cuando inicia sesión con "beto@example.com" y "ClaveBeto-2026"
    Entonces el sistema pide esperar antes de intentar de nuevo
    Y la acción "login_bloqueado" queda en la auditoría

  Esquema del escenario: Un intento de inyección no entra
    Cuando inicia sesión con "<correo>" y "<clave>"
    Entonces no entra al sistema

    Ejemplos:
      | correo                       | clave       |
      | beto@example.com' OR '1'='1  | x           |
      | beto@example.com             | ' OR '1'='1 |
      | beto@example.com--           | x           |
