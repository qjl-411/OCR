FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY scripts scripts
COPY model-parts model-parts
COPY backend backend
COPY dist dist
COPY models models
COPY data data
RUN python scripts/restore_models.py
ENV INVOICE_DATA_DIR=/data INVOICE_SEED_DEMO=1 PYTHONUNBUFFERED=1
RUN mkdir -p /data
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
