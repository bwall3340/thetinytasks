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

# Copy root-level static site files for the home page and other tools
COPY index.html /app/site/index.html
COPY styles.css /app/site/styles.css
COPY shared.css /app/site/shared.css
COPY script.js /app/site/script.js
COPY background-remover.html /app/site/background-remover.html
COPY return-stream.html /app/site/return-stream.html
COPY data-finder.html /app/site/data-finder.html
COPY about.html /app/site/about.html
COPY bigger-projects.html /app/site/bigger-projects.html
COPY assets/ /app/site/assets/
COPY Sankey/ /app/site/Sankey/
COPY WhiteBackgroundRemover/ /app/site/WhiteBackgroundRemover/

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --preload
