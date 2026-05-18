"""
Servicio gRPC: MultiplicacionService
Recibe un mensaje Numeros y devuelve el producto en un mensaje Respuesta.
Uso:
    python3 multiplicacion_service.py --port 50053 --rabbitmq-host 192.168.1.10
"""
import argparse
import logging
from concurrent import futures

import grpc
from protos import calculadora_pb2, calculadora_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MUL] %(message)s")


class MultiplicacionServicer(calculadora_pb2_grpc.MultiplicacionServiceServicer):
    """Implementación del servicio de multiplicación."""

    def Multiplicar(self, request, context):
        try:
            resultado = request.num1 * request.num2
            logging.info(f"Multiplicar({request.num1}, {request.num2}) = {resultado}")
            return calculadora_pb2.Respuesta(data=resultado)
        except Exception as e:
            logging.error(f"Error en Multiplicar: {e}")
            return calculadora_pb2.Respuesta(error=str(e))


def serve(port: int):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_MultiplicacionServiceServicer_to_server(
        MultiplicacionServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"MultiplicacionService escuchando en puerto {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio gRPC de Multiplicación")
    parser.add_argument("--port", type=int, default=50053, help="Puerto gRPC")
    parser.add_argument("--rabbitmq-host", type=str, default="localhost",
                        help="IP del servidor RabbitMQ (reservado para el worker)")
    args = parser.parse_args()
    serve(args.port)
