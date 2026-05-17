#!/usr/bin/env python3
import sys, os, signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'proto'))

import grpc
from concurrent import futures
import calculadora_pb2
import calculadora_pb2_grpc

PORT = os.environ.get("GRPC_PORT", "50053")

class MultiplicacionServicer(calculadora_pb2_grpc.MultiplicacionServicer):
    def Calcular(self, request, context):
        resultado = request.num1 * request.num2
        print(f"[MULT] {request.num1} × {request.num2} = {resultado}")
        return calculadora_pb2.Respuesta(data=resultado)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_MultiplicacionServicer_to_server(MultiplicacionServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"[MULT] Escuchando en puerto {PORT}")
    def _stop(sig, frame): server.stop(0); sys.exit(0)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT,  _stop)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()