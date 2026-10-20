"""Servidor SMTP mínimo para pruebas: acepta todo y guarda cada mensaje como .eml en la carpeta indicada."""
import itertools
import socketserver
import sys
from pathlib import Path

SALIDA = Path(sys.argv[1])
PUERTO = int(sys.argv[2]) if len(sys.argv) > 2 else 2525
SALIDA.mkdir(parents=True, exist_ok=True)
contador = itertools.count(1)


class Manejador(socketserver.StreamRequestHandler):
    def responder(self, texto):
        self.wfile.write((texto + "\r\n").encode())

    def handle(self):
        self.responder("220 captura ESMTP")
        while True:
            linea = self.rfile.readline()
            if not linea:
                return
            cmd = linea.decode("utf-8", "replace").strip().upper()
            if cmd.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-captura\r\n250 SIZE 10000000\r\n")
            elif cmd.startswith(("MAIL", "RCPT", "RSET", "NOOP")):
                self.responder("250 OK")
            elif cmd == "DATA":
                self.responder("354 Fin con <CRLF>.<CRLF>")
                partes = []
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b".\n", b""):
                        break
                    partes.append(l[1:] if l.startswith(b"..") else l)
                (SALIDA / f"{next(contador):03d}.eml").write_bytes(b"".join(partes))
                self.responder("250 Guardado")
            elif cmd == "QUIT":
                self.responder("221 Adios")
                return
            else:
                self.responder("502 No implementado")


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


print(f"SMTP de captura en 127.0.0.1:{PUERTO} -> {SALIDA}", flush=True)
Servidor(("127.0.0.1", PUERTO), Manejador).serve_forever()
