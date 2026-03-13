FROM python:3.11-slim

# Install system deps needed by Playwright and pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Install Playwright browsers (Chromium only)
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
