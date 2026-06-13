#!/bin/bash
set -e

echo "🐘 Starting PostgreSQL..."
service postgresql start

# Wait for postgres to boot
until pg_isready; do
  sleep 1
done

# Set password for postgres database user so Flyway and uvicorn can authenticate via TCP
runuser -l postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres';\""

# Create database and pgvector extension using unix socket peer authentication
runuser -l postgres -c "psql -c \"CREATE DATABASE unidocverse_db;\"" || true
runuser -l postgres -c "psql -d unidocverse_db -c \"CREATE EXTENSION IF NOT EXISTS vector;\"" || true

# Run Flyway migrations
echo "🛠 Running Flyway migrations..."
flyway -url=jdbc:postgresql://localhost:5432/unidocverse_db -user=postgres -password=postgres -locations=filesystem:/app/migrations migrate || true

echo "🤖 Starting Ollama..."
ollama serve &

# Export database configurations for the backend application
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres

echo "🚀 Starting UniDocVerse Backend and Frontend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 80

