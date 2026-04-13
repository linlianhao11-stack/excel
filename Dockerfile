FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /build/../backend/static ./backend/static/
COPY nginx.conf /etc/nginx/sites-enabled/default

RUN mkdir -p /data/work /data/db

EXPOSE 80

CMD nginx && uvicorn backend.main:app --host 127.0.0.1 --port 8000
