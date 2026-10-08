# Guardia Viva en un solo servicio (D05): FastAPI atiende /api y sirve la compilación del frontend.
# Se construye desde la raíz del repo:  docker build -t guardia-viva .

# --- Etapa 1: compilar el frontend ---
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Vite incrusta estas variables al compilar: tienen que llegar como argumentos de compilación.
# Son la URL y la clave pública (anon) de Supabase; no son secretos de servidor.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

# --- Etapa 2: backend con la compilación adentro ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/ backend/
# Instalación editable: app/main.py queda en /app/backend y busca la compilación en /app/frontend/dist.
RUN pip install --no-cache-dir -e ./backend
COPY --from=frontend /frontend/dist frontend/dist

RUN useradd --create-home --uid 10001 guardia && chown -R guardia /app
USER guardia
WORKDIR /app/backend

# Render define PORT; en local el servicio queda en el 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
