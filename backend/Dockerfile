FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Backend code
COPY backend/app.py     /app/app.py
COPY backend/db/        /app/db/
COPY backend/providers/ /app/providers/
COPY backend/cli/       /app/cli/

# Frontend assets served by FastAPI
COPY frontend/static/    /app/static/
COPY frontend/templates/ /app/templates/

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
