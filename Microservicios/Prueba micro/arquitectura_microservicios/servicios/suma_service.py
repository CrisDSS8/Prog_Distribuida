"""
Servicio gRPC: SumaService
Recibe un mensaje Numeros y devuelve la suma en un mensaje Respuesta.
Uso:
    python3 suma_service.py --port 50051 --rabbitmq-host 192.168.1.10
"""
import argparse
import logging
from concurrent import futures

import grpc
from protos import calculadora_pb2, calculadora_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SUMA] %(message)s")


class SumaServicer(calculadora_pb2_grpc.SumaServiceServicer):
    """Implementación del servicio de suma."""

    def Sumar(self, request, context):
        try:
            resultado = request.num1 + request.num2
            logging.info(f"Sumar({request.num1}, {request.num2}) = {resultado}")
            return calculadora_pb2.Respuesta(data=resultado)
        except Exception as e:
            logging.error(f"Error en Sumar: {e}")
            return calculadora_pb2.Respuesta(error=str(e))


def serve(port: int):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_SumaServiceServicer_to_server(SumaServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"SumaService escuchando en puerto {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio gRPC de Suma")
    parser.add_argument("--port", type=int, default=50051, help="Puerto gRPC")
    parser.add_argument("--rabbitmq-host", type=str, default="localhost",
                        help="IP del servidor RabbitMQ (reservado para el worker)")
    args = parser.parse_args()
    serve(args.port)
