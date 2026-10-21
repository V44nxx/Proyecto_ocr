#!/bin/sh
# Arranque del backend: el contenedor empieza como root solo para dejar las carpetas de datos a nombre
# del usuario kondid (los volúmenes que ya existen traen archivos de root) y después corre la aplicación
# sin privilegios. Si algo lograra ejecutar código dentro del contenedor, no tendría permisos de root.
set -e

if [ "$(id -u)" = "0" ]; then
    for carpeta in /app/uploads /app/exports /app/logs /app/credentials; do
        mkdir -p "$carpeta" 2>/dev/null || true
        # Un montaje de solo lectura (las credenciales) no se puede cambiar: se deja como está
        find "$carpeta" ! -user kondid -exec chown kondid:kondid {} + 2>/dev/null || true
    done

    # Credenciales de Google montadas que el usuario no puede leer: se usa una copia privada suya
    if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ] \
        && ! setpriv --reuid=kondid --regid=kondid --init-groups test -r "$GOOGLE_APPLICATION_CREDENTIALS"; then
        copia=/home/kondid/google-credentials.json
        install -o kondid -g kondid -m 600 "$GOOGLE_APPLICATION_CREDENTIALS" "$copia"
        export GOOGLE_APPLICATION_CREDENTIALS="$copia"
    fi

    exec setpriv --reuid=kondid --regid=kondid --init-groups "$@"
fi

exec "$@"
