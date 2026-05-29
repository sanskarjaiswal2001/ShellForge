FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

# Install deps
RUN uv pip install --system -e .

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Pre-download GLiNER model at build time so startup is fast
# Comment out for faster builds; model downloads at first request instead.
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('knowledgator/gliner-pii-base-v1.0')" || true

EXPOSE 8888
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8888"]
