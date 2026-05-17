"""
Servicio gRPC: RestaService
Recibe un mensaje Numeros y devuelve la resta (a - b) en un mensaje Respuesta.
Uso:
    python3 resta_service.py --port 50052 --rabbitmq-host 192.168.1.10
"""
import argparse
import logging
from concurrent import futures

import grpc
from protos import calculadora_pb2, calculadora_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [RESTA] %(message)s")


class RestaServicer(calculadora_pb2_grpc.RestaServiceServicer):
    """Implementación del servicio de resta."""

    def Restar(self, request, context):
        try:
            resultado = request.num1 - request.num2
            logging.info(f"Restar({request.num1}, {request.num2}) = {resultado}")
            return calculadora_pb2.Respuesta(data=resultado)
        except Exception as e:
            logging.error(f"Error en Restar: {e}")
            return calculadora_pb2.Respuesta(error=str(e))


def serve(port: int):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_RestaServiceServicer_to_server(RestaServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"RestaService escuchando en puerto {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio gRPC de Resta")
    parser.add_argument("--port", type=int, default=50052, help="Puerto gRPC")
    parser.add_argument("--rabbitmq-host", type=str, default="localhost",
                        help="IP del servidor RabbitMQ (reservado para el worker)")
    args = parser.parse_args()
    serve(args.port)
