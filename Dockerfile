# ==========================================
# STAGE 1: Build Angular Frontend
# ==========================================
FROM node:20 AS frontend-builder
WORKDIR /app
COPY unidocverse-dashboard/package*.json ./
RUN npm install --loglevel=error
COPY unidocverse-dashboard/ .
RUN npm run build -- --configuration=production

# ==========================================
# STAGE 2: Build Python Backend & Bundle Everything
# ==========================================
FROM python:3.11-slim

WORKDIR /app

ENV FLYWAY_VERSION=10.16.0 \
    OLLAMA_MODEL=phi3:mini \
    DB_PORT=54321 \
    DB_USER=postgres \
    DB_PASSWORD=postgres

# Install all system dependencies, pgvector, Flyway, Ollama, and Python packages
# in a single layer to minimise intermediate layers
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
    # ── pgvector ───────────────────────────────────────────────────────────
    && git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector && make OPTFLAGS="" && make install \
    && cd /app && rm -rf /tmp/pgvector \
    # ── Flyway ────────────────────────────────────────────────────────────
    && curl -L https://repo1.maven.org/maven2/org/flywaydb/flyway-commandline/$FLYWAY_VERSION/flyway-commandline-$FLYWAY_VERSION.tar.gz \
       | tar xz -C /usr/local/ \
    && ln -s /usr/local/flyway-$FLYWAY_VERSION/flyway /usr/local/bin/flyway \
    # ── Ollama ────────────────────────────────────────────────────────────
    && curl -fsSL https://ollama.com/install.sh | sh \
    # ── Python packages ───────────────────────────────────────────────────
    && pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir paddlepaddle==3.2.2 -f https://www.paddlepaddle.org.cn/whl/linux/cpu/openblas/html \
    # ── Purge build-only tools ────────────────────────────────────────────
    && apt-get purge -y --auto-remove \
       git \
       build-essential \
       postgresql-server-dev-all \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies separately so Docker can cache this layer
COPY unidocverse-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Bake phi3:mini into the image so it works offline ─────────────────────────
# Start Ollama as a background daemon, pull the model, then stop the daemon.
# The model blobs are stored in /root/.ollama and persist into the final image.
RUN OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve &\
    OLLAMA_PID=$! && \
    echo "Waiting for Ollama to start..." && \
    for i in $(seq 1 60); do curl -sf http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 1; done && \
    echo "Pulling phi3:mini..." && \
    ollama pull phi3:mini && \
    echo "phi3:mini baked ✓" && \
    kill $OLLAMA_PID && wait $OLLAMA_PID 2>/dev/null || true

# Copy backend source code and compile to bytecode
COPY unidocverse-service/app/ ./app/
COPY unidocverse-service/migrations/ ./migrations/
RUN mkdir -p ./models
RUN python -m compileall -b app && find app -name "*.py" -delete

# Copy Angular frontend (FastAPI serves these as static files)
COPY --from=frontend-builder /app/dist/ /app/unidocverse-dashboard/dist/

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
