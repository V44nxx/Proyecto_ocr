from passlib.context import CryptContext
import subprocess
import os

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
hash_val = pwd_context.hash('Admin123!')

env = os.environ.copy()
env['PGPASSWORD'] = '123456'

cmd = [
    r'C:\Program Files\PostgreSQL\18\bin\psql.exe',
    '-U', 'postgres',
    '-h', 'localhost',
    '-p', '5432',
    '-d', 'proyecto_ocr_db',
    '-c', f"UPDATE usuarios SET password_hash='{hash_val}' WHERE email='admin@ocr.com';"
]

result = subprocess.run(cmd, env=env, capture_output=True, text=True)
print("Resultado:", result.stdout, result.stderr)
