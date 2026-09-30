FROM node:22-slim AS frontend-build
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ANPR_DATABASE=/app/data/nexus.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home nexus
COPY anpr ./anpr
COPY tools ./tools
COPY demo.py README.md ./
COPY samples ./samples
COPY --from=frontend-build /ui/dist ./frontend/dist
COPY frontend/public ./frontend/public
RUN mkdir -p /app/data /app/output && chown -R nexus:nexus /app
USER nexus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "anpr.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
