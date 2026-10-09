FROM python:3.12-slim

WORKDIR /app

# System deps needed by some scientific Python wheels (TensorFlow / XGBoost
# build scripts) and for the RAG embedding model (ONNX runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so the heavier app/data layers can change without
# invalidating the pip cache.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the all-MiniLM-L6-v2 ONNX weights so the first chat request
# doesn't pay the 30s model download.  Cached in /tmp so it's fast to warm
# up on container start.  fastembed uses HF_HUB_CACHE to find them.
ENV RAG_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from fastembed import TextEmbedding; m=TextEmbedding('${RAG_EMBED_MODEL}'); \
    list(m.embed(['warm-up']))" || true

# Backend code and model artifacts.
COPY backend/app/ ./app/
COPY backend/models/ ./models/

# Reference data (xlsx / csv / geojson).  Both layouts are kept so the
# seeder can find the files regardless of which path it prefers:
#   - /app/data/  (backend/data/    - slim backend-only checkout)
#   - /data/      (repo-root/data/  - normal project layout)
COPY data/ ./data/
COPY data/ /data/

# Pre-create the directory the runtime GeoJSON seeder expects, even if the
# build context currently has zero GeoJSON files (so future volumes mounted
# there will just work).
RUN mkdir -p /app/data/geo_exports /data/geo_exports

# .env is intentionally NOT copied (see .dockerignore).  Pass DATABASE_URL,
# JWT_SECRET_KEY, and other secrets via real environment variables in your
# hosting platform.

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]