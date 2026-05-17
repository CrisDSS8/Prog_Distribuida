#!/usr/bin/env python3
import sys, os, signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'proto'))

import grpc
from concurrent import futures
import calculadora_pb2
import calculadora_pb2_grpc

PORT = os.environ.get("GRPC_PORT", "50054")

class DivisionServicer(calculadora_pb2_grpc.DivisionServicer):
    def Calcular(self, request, context):
        if request.num2 == 0:
            print(f"[DIV] ERROR división por cero")
            return calculadora_pb2.Respuesta(error="División por cero no permitida")
        resultado = request.num1 / request.num2
        print(f"[DIV] {request.num1} ÷ {request.num2} = {resultado}")
        return calculadora_pb2.Respuesta(data=resultado)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_DivisionServicer_to_server(DivisionServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"[DIV] Escuchando en puerto {PORT}")
    def _stop(sig, frame): server.stop(0); sys.exit(0)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT,  _stop)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()