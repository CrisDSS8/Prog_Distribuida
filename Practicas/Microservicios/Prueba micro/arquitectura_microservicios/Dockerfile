FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar protos y regenerar stubs dentro del contenedor
COPY protos/ ./protos/
RUN python -m grpc_tools.protoc \
      -I./protos \
      --python_out=./protos \
      --grpc_python_out=./protos \
      protos/calculadora.proto \
    && sed -i \
      's/^import calculadora_pb2 as calculadora__pb2/from protos import calculadora_pb2 as calculadora__pb2/' \
      protos/calculadora_pb2_grpc.py

# Copiar resto del código
COPY servicios/ ./servicios/
COPY orquestador_server.py .
COPY cliente.py .

# Python encuentra los módulos desde /app
ENV PYTHONPATH=/app

EXPOSE 50051
CMD ["python3", "servicios/suma_service.py"]