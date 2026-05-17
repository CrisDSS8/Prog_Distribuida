#!/usr/bin/env python3
import subprocess, sys

cmd = [
    sys.executable, "-m", "grpc_tools.protoc",
    "--proto_path=proto",
    "--python_out=proto",
    "--grpc_python_out=proto",
    "proto/calculadora.proto",
]

print("Generando código gRPC …")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR:", result.stderr)
    sys.exit(1)
print("Listo. Archivos generados en proto/")