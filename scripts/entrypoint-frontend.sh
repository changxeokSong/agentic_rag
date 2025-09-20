#!/usr/bin/env sh
set -e

echo "[frontend] Waiting for database..."
python - <<'PY'
import os, time
import psycopg2

host = os.getenv('PG_DB_HOST','postgres')
port = int(os.getenv('PG_DB_PORT','5432'))
db = os.getenv('PG_DB_NAME','synergy')
user = os.getenv('PG_DB_USER','synergy')
pwd = os.getenv('PG_DB_PASSWORD','synergy')

for i in range(60):
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pwd)
        conn.close()
        print('[frontend] DB ready')
        break
    except Exception as e:
        print('[frontend] DB not ready yet...', e)
        time.sleep(2)
else:
    print('[frontend] DB readiness timed out')
PY

exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0


