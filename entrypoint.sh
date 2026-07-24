#!/bin/bash
set -e

# Restrict multi-threaded ML libraries to 4 CPU threads to prevent host system lag/freezes
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export VECLIB_MAXIMUM_THREADS=4
export NUMEXPR_NUM_THREADS=4

# Change PostgreSQL port to 54321 inside the container
sed -i "s/#port = 5432/port = 54321/g" /etc/postgresql/17/main/postgresql.conf
sed -i "s/port = 5432/port = 54321/g" /etc/postgresql/17/main/postgresql.conf

echo "🐘 Starting PostgreSQL..."
service postgresql start

# Wait for postgres to boot on port 54321
until pg_isready -p 54321; do
  sleep 1
done

# Set password for postgres database user so Flyway and uvicorn can authenticate via TCP
runuser -l postgres -c "psql -p 54321 -c \"ALTER USER postgres PASSWORD 'postgres';\""

# Create database and pgvector extension using unix socket peer authentication
runuser -l postgres -c "psql -p 54321 -c \"CREATE DATABASE unidocverse_db;\"" || true
runuser -l postgres -c "psql -p 54321 -d unidocverse_db -c \"CREATE EXTENSION IF NOT EXISTS vector;\"" || true

# Run Flyway migrations
echo "🛠 Running Flyway migrations..."
flyway -url=jdbc:postgresql://localhost:54321/unidocverse_db -user=postgres -password=postgres -locations=filesystem:/app/migrations migrate || true

echo "🤖 Starting Ollama..."
OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve &
OLLAMA_PID=$!

# Wait for Ollama HTTP API to become ready (up to 60s)
echo "⏳ Waiting for Ollama to become ready..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is ready"
    break
  fi
  sleep 1
done

# Pull phi3:mini if not already cached
if ollama list 2>/dev/null | grep -q "phi3:mini"; then
  echo "✅ phi3:mini already cached — skipping pull"
else
  echo "📥 Pulling phi3:mini (first run — this may take a few minutes)..."
  ollama pull phi3:mini || echo "⚠️  phi3:mini pull failed — AI features may be limited until model is available"
fi

# Export database configurations for the backend application
export DB_PORT=54321
export DB_USER=postgres
export DB_PASSWORD=postgres

echo "🚀 Starting UniDocVerse Backend and Frontend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 80

