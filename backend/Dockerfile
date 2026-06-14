# Orca backend — FastAPI. Build: docker build -t orca-api backend/
# Run:   docker run -p 8000:8000 orca-api
FROM python:3.12-slim

WORKDIR /app
COPY requirements-demo.txt requirements.txt ./
# local-demo deps are enough to run; add requirements.txt for live Azure Foundry
RUN pip install --no-cache-dir -r requirements-demo.txt

COPY app ./app
ENV ORACLE_HOST=0.0.0.0 ORACLE_PORT=8000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
