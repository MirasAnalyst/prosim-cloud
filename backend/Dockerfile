FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for pip compilation.
# Note: add mono-complete here to enable DWSIM/pythonnet integration.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects PORT env var; default to 8000 for local use
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
