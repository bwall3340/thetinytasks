FROM python:3.11

WORKDIR /app

COPY WSR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY WSR/ .

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
