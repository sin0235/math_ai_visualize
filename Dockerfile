FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQLITE_PATH=/app/data/hinh.db \
    PADDLEOCR_HOME=/app/models/ocr/paddleocr \
    TORCH_HOME=/app/models/ocr/torch \
    HF_HOME=/app/models/ocr/huggingface
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor libgomp1 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./backend/requirements.txt
COPY backend/requirements-ocr.txt ./backend/requirements-ocr.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-ocr.txt
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mkdir -p /app/data /run/nginx
EXPOSE 8080
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
