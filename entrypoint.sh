#!/bin/bash
set -e

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

# Export database configurations for the backend application
export DB_PORT=54321
export DB_USER=postgres
export DB_PASSWORD=postgres

echo "🚀 Starting UniDocVerse Backend and Frontend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 80

