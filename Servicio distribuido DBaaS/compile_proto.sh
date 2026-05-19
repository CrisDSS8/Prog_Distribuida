#!/bin/bash
# compile_proto.sh
# Compila dbaas.proto y deposita el resultado en protos/generated/
# Ejecutar desde la raíz del proyecto: bash compile_proto.sh

set -e

PROTO_DIR="./protos"
OUT_DIR="./protos/generated"

mkdir -p "$OUT_DIR"

# crear __init__.py para que Python lo trate como paquete
touch "$OUT_DIR/__init__.py"

echo "compilando dbaas.proto..."

python -m grpc_tools.protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  "$PROTO_DIR/dbaas.proto"

echo "listo → $OUT_DIR"
echo "archivos generados:"
ls "$OUT_DIR"
