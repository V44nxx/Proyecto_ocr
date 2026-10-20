# language: es
Característica: Recuperar la contraseña por correo
  Como usuaria de KondID que olvidó su contraseña
  Quiero recibir en mi correo un enlace para elegir una nueva
  Para volver a entrar sin pedirle ayuda al administrador

  Antecedentes:
    Dado que existe la usuaria "ana@example.com" con la contraseña "ClaveVieja-2026"
    Y el envío de correos está configurado

  Escenario: La usuaria no recuerda la contraseña y la cambia con el enlace del correo
    Dado que la usuaria tiene una sesión abierta con la contraseña vieja
    Cuando pide un enlace de recuperación para "ana@example.com"
    Entonces recibe un correo con un enlace para restablecer la contraseña
    Cuando abre el enlace y escribe la contraseña nueva "Rio-Verde-Tarde-7"
    Entonces puede entrar con la contraseña "Rio-Verde-Tarde-7"
    Y ya no puede entrar con la contraseña "ClaveVieja-2026"
    Y la sesión que tenía abierta se cierra

  Escenario: El enlace del correo sirve una sola vez
    Dado que la usuaria ya cambió la contraseña con un enlace
    Cuando abre el mismo enlace y escribe la contraseña nueva "Otra-Clave-Larga-9"
    Entonces el sistema responde que el enlace no es válido o ya venció

  Escenario: Pedir el enlace no revela si un correo está registrado
    Cuando pide un enlace de recuperación para "nadie@example.com"
    Entonces la respuesta es la misma que para un correo registrado
    Y no se envía ningún correo

  Escenario: No se acepta una contraseña nueva demasiado común
    Dado que la usuaria pidió un enlace de recuperación
    Cuando abre el enlace y escribe la contraseña nueva "Password123!"
    Entonces el sistema rechaza la contraseña por ser muy común
    Y puede entrar con la contraseña "ClaveVieja-2026"
