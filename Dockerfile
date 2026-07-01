# ==========================================
# STAGE 1: Build Angular Frontend
# ==========================================
FROM node:20 AS frontend-builder
WORKDIR /app
COPY unidocverse-dashboard/package*.json ./
RUN npm install
COPY unidocverse-dashboard/ .
RUN npm run build -- --configuration=production

# ==========================================
# STAGE 2: Build Python Backend & Bundle Everything
# ==========================================
FROM python:3.11-slim

WORKDIR /app

ENV FLYWAY_VERSION=10.16.0
# Install system dependencies (Postgres, OCR engines, Git, Curl, Zstd, Dev Headers)
RUN apt-get update && apt-get install -y \
    postgresql \
    postgresql-contrib \
    postgresql-client \
    postgresql-server-dev-all \
    libpq-dev \
    tesseract-ocr \
    ghostscript \
    curl \
    git \
    zstd \
    build-essential \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama natively
RUN curl -fsSL https://ollama.com/install.sh | sh

# Compile and install pgvector extension inside Postgres
RUN git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make OPTFLAGS="" && make install \
    && rm -rf /tmp/pgvector

# Install Flyway CLI (architecture-independent, using system JRE)
RUN curl -L https://repo1.maven.org/maven2/org/flywaydb/flyway-commandline/$FLYWAY_VERSION/flyway-commandline-$FLYWAY_VERSION.tar.gz \
    | tar xz -C /usr/local/ \
    && ln -s /usr/local/flyway-$FLYWAY_VERSION/flyway /usr/local/bin/flyway

# Copy python dependencies and install
COPY unidocverse-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code, migrations, and pre-downloaded models
COPY unidocverse-service/app/ ./app/
COPY unidocverse-service/migrations/ ./migrations/
COPY unidocverse-service/models/ ./models/
RUN python -m compileall -b app && find app -name "*.py" -delete

# Copy Angular frontend static files (FastAPI serves these)
COPY --from=frontend-builder /app/dist/ /app/unidocverse-dashboard/dist/

# Pre-package the staged Ollama models (so the client doesn't need to download phi3:mini)
COPY build/ollama_models/ /root/.ollama/models/

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose HTTP port
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
