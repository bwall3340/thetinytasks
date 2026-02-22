FROM python:3.11

WORKDIR /app

# Runtime libraries required by opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY WSR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY WSR/ .

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --preload
