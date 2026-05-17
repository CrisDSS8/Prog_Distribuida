"""
Servicio gRPC: DivisionService
Recibe un mensaje Numeros y devuelve el cociente (a / b) en un mensaje Respuesta.
Si b == 0, retorna un mensaje Respuesta con campo error.
Uso:
    python3 division_service.py --port 50054 --rabbitmq-host 192.168.1.10
"""
import argparse
import logging
from concurrent import futures

import grpc
from protos import calculadora_pb2, calculadora_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DIV] %(message)s")


class DivisionServicer(calculadora_pb2_grpc.DivisionServiceServicer):
    """Implementación del servicio de división con validación de divisor cero."""

    def Dividir(self, request, context):
        try:
            if request.num2 == 0.0:
                msg = f"División entre cero: {request.num1} / {request.num2}"
                logging.warning(msg)
                return calculadora_pb2.Respuesta(error=msg)

            resultado = request.num1 / request.num2
            logging.info(f"Dividir({request.num1}, {request.num2}) = {resultado}")
            return calculadora_pb2.Respuesta(data=resultado)
        except Exception as e:
            logging.error(f"Error en Dividir: {e}")
            return calculadora_pb2.Respuesta(error=str(e))


def serve(port: int):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculadora_pb2_grpc.add_DivisionServiceServicer_to_server(DivisionServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"DivisionService escuchando en puerto {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servicio gRPC de División")
    parser.add_argument("--port", type=int, default=50054, help="Puerto gRPC")
    parser.add_argument("--rabbitmq-host", type=str, default="localhost",
                        help="IP del servidor RabbitMQ (reservado para el worker)")
    args = parser.parse_args()
    serve(args.port)
