#!/usr/bin/env python3
import sys, os, signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'proto'))

import grpc
from concurrent import futures
import calculadora_pb2
import calculadora_pb2_grpc

PORT = os.environ.get("GRPC_PORT", "50052")

class RestaServicer(calculadora_pb2_grpc.RestaServicer):
    def Calcular(self, request, context):
        resultado = request.num1 - request.num2
        print(f"[RESTA] {request.num1} - {request.num2} = {resultado}")
        return calculadora_pb2.Respuesta(data=resultado)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_RestaServicer_to_server(RestaServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"[RESTA] Escuchando en puerto {PORT}")
    def _stop(sig, frame): server.stop(0); sys.exit(0)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT,  _stop)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()