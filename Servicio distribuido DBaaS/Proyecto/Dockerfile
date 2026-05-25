# Dockerfile
# Dockerfile compartido para todos los microservicios.
# Se construye con: docker build --build-arg SERVICE=ms-auth .
# El docker-compose.yml pasa el ARG automáticamente a cada servicio.

FROM python:3.11-slim

# argumento que indica qué microservicio construir
ARG SERVICE
ENV SERVICE=${SERVICE}

WORKDIR /app

# ── usuario no-root (requerido por MPI) ───────────────────────────────────────
RUN useradd -m -u 1000 dbaas

# ── dependencias del sistema para mpi4py (solo ms-query lo necesita) ──────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenmpi-dev \
    openmpi-bin \
    && rm -rf /var/lib/apt/lists/*

# ── copiar proto y compilarlo ─────────────────────────────────────────────────
COPY protos/ ./protos/

# ── copiar requirements del servicio e instalar ───────────────────────────────
COPY ${SERVICE}/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Instalar explícitamente la herramienta de compilación para todos
RUN pip install --no-cache-dir grpcio-tools

# ── compilar proto dentro del contenedor ─────────────────────────────────────
RUN python -m grpc_tools.protoc \
    -I./protos \
    --python_out=./protos \
    --grpc_python_out=./protos \
    protos/dbaas.proto && \
    sed -i 's/from\. import dbaas_pb2/import dbaas_pb2/' protos/dbaas_pb2_grpc.py

# ── copiar código del servicio ────────────────────────────────────────────────
COPY ${SERVICE}/ ./${SERVICE}/

# dar permisos al usuario no-root y cambiar a él
RUN chown -R dbaas:dbaas /app
USER dbaas

# el CMD lo sobreescribe docker-compose por servicio
CMD ["python", "-m", "ms-auth.auth_server"]
