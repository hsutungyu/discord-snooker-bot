# Stage 1: build dependencies (asyncpg requires gcc to compile its C extension)
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: lean runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (env vars injected at runtime via k8s Secret)
COPY bot.py config.py ./
COPY engine/ engine/
COPY db/ db/
COPY cogs/ cogs/

# Run as non-root
RUN useradd -m botuser && chown -R botuser /app
USER botuser

CMD ["python", "-u", "bot.py"]
