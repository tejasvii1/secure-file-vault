FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/vault.db \
    UPLOAD_DIR=/data/uploads

WORKDIR /app

# install dependencies first so this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py auth.py database.py models.py ./

# run as an unprivileged user; /data is the only place the app writes to
RUN useradd --create-home --uid 1000 vault \
    && mkdir -p /data/uploads \
    && chown -R vault:vault /data
USER vault
VOLUME /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
