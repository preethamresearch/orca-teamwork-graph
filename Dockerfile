# Orca — single-service image: FastAPI serves the API and the web app.
# Build:  docker build -t orca .
# Run:    docker run -p 8000:8000 orca   → open http://localhost:8000
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt
COPY backend/app ./app
COPY web ./web
COPY mcp ./mcp
ENV ORCA_WEB_DIR=/app/web \
    ORCA_MCP_SERVER=/app/mcp/demo_resource_server.py \
    ORACLE_HOST=0.0.0.0
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
