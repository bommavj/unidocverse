#!/bin/bash
set -e

# Lite image: Postgres + backend only. Answers come from Ollama on the host
# (OLLAMA_HOST, default http://host.docker.internal:11434) or a cloud model.

export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export VECLIB_MAXIMUM_THREADS=4
export NUMEXPR_NUM_THREADS=4

sed -i "s/#port = 5432/port = 54321/g" /etc/postgresql/17/main/postgresql.conf
sed -i "s/port = 5432/port = 54321/g" /etc/postgresql/17/main/postgresql.conf

echo "🐘 Starting PostgreSQL..."
service postgresql start
until pg_isready -p 54321; do
  sleep 1
done

runuser -l postgres -c "psql -p 54321 -c \"ALTER USER postgres PASSWORD 'postgres';\""
runuser -l postgres -c "psql -p 54321 -c \"CREATE DATABASE unidocverse_db;\"" || true
runuser -l postgres -c "psql -p 54321 -d unidocverse_db -c \"CREATE EXTENSION IF NOT EXISTS vector;\"" || true

echo "🛠 Running Flyway migrations..."
flyway -url=jdbc:postgresql://localhost:54321/unidocverse_db -user=postgres -password=postgres -locations=filesystem:/app/migrations -mixed=true -postgresql.transactional.lock=false migrate || true

if curl -sf "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
  echo "✅ Ollama found at ${OLLAMA_HOST}"
else
  echo "ℹ️  No Ollama at ${OLLAMA_HOST}. Install Ollama on this computer (ollama.com) and run"
  echo "   'ollama pull mistral:7b', or add a cloud model in Integrations. Search and uploads work meanwhile."
fi

export DB_PORT=54321
export DB_USER=postgres
export DB_PASSWORD=postgres

echo "🚀 Starting UniDocVerse (Lite)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 7979
