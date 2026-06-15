#!/bin/sh
# Entrypoint de Tyrion.
# Primer argumento: "api" (default) o "worker".

set -e

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a PostgreSQL en ${DATABASE_URL:-db:5432}…"
until python -c "
import psycopg2, os, sys
url = os.environ.get('DATABASE_URL','')
# Extraer host/port de DATABASE_URL o usar defaults
import re
m = re.search(r'@([^:/]+):?(\d+)?/', url)
host = m.group(1) if m else 'db'
port = int(m.group(2)) if m and m.group(2) else 5432
try:
    psycopg2.connect(host=host, port=port, dbname='tyrion', user='tyrion', password='tyrion')
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    echo "  PostgreSQL no disponible aún, reintentando…"
    sleep 2
done
echo "✅ PostgreSQL listo."

# Aplicar migraciones en orden
echo "🗄  Aplicando migraciones…"
python - <<'PYEOF'
import psycopg2, os, glob

url = os.environ.get('DATABASE_URL', '')
import re
m = re.search(r'@([^:/]+):?(\d+)?/(\w+)', url)
host = m.group(1) if m else 'db'
port = int(m.group(2)) if m and m.group(2) else 5432
dbname = m.group(3) if m else 'tyrion'

conn = psycopg2.connect(host=host, port=port, dbname=dbname, user='tyrion', password='tyrion')
conn.autocommit = True
cur = conn.cursor()

migration_dir = '/app/migrations'
files = sorted(glob.glob(f'{migration_dir}/*.sql'))
for f in files:
    print(f'  → {f}')
    with open(f) as fh:
        sql = fh.read()
    try:
        cur.execute(sql)
        print(f'    ✓')
    except psycopg2.errors.DuplicateObject:
        print(f'    (ya existía, omitido)')
    except Exception as e:
        print(f'    ⚠ {e}')

cur.close()
conn.close()
print('Migraciones completadas.')
PYEOF

# Modo de ejecución
CMD="${1:-api}"

if [ "$CMD" = "api" ]; then
    echo "🚀 Iniciando API en 0.0.0.0:8000…"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
elif [ "$CMD" = "worker" ]; then
    echo "⏰ Iniciando worker de timers (cada 30 s)…"
    exec python -c "
import asyncio, time, sys
sys.path.insert(0, '/app')
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services.motor_cotejo import MotorCotejo

# En producción el repo sería contra PostgreSQL.
# Aquí usamos el repo en memoria (suficiente para dev sin BD real).
repo = RepositorioEnMemoria()
pipeline = Pipeline(repo=repo, motor=MotorCotejo())

print('Worker de timers activo. Intervalo: 30 s.')
while True:
    try:
        nuevos = pipeline.ejecutar_timers()
        if nuevos:
            print(f'  {len(nuevos)} mensaje(s) preparado(s) por timers.')
    except Exception as e:
        print(f'  Error en worker: {e}')
    time.sleep(30)
"
else
    echo "CMD desconocido: $CMD (usar 'api' o 'worker')"
    exit 1
fi
