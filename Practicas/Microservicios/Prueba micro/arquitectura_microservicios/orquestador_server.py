"""
orquestador_server.py — Servidor gRPC del orquestador con soporte paralelo.

Cada petición corre en su propio hilo y tiene su propio ID para
correlacionar cliente ↔ respuesta cuando hay múltiples peticiones simultáneas.

Uso en Docker Compose:
    python3 orquestador_server.py
        --port 50060
        --rabbitmq-host rabbitmq
        --grpc-host-suma suma_service
        --grpc-host-resta resta_service
        --grpc-host-mul multiplicacion_service
        --grpc-host-div division_service

Uso local:
    python3 orquestador_server.py --port 50060
"""

import argparse
import logging
import uuid
import re
from concurrent import futures

import grpc
import pika

from protos import calculadora_pb2, calculadora_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ORQUESTADOR] %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)

EXCHANGE = "calculadora_exchange"

OPERACIONES = {
    "+": ("add", "cola_suma"),
    "-": ("sub", "cola_resta"),
    "*": ("mul", "cola_multiplicacion"),
    "/": ("div", "cola_division"),
}

PRECEDENCIA = {"*": 2, "/": 2, "+": 1, "-": 1}


# ── Parser ────────────────────────────────────────────────────────────────────

def tokenizar(expr: str) -> list:
    expr = expr.replace(" ", "")
    tokens = []
    for p in re.compile(r"(\d+\.?\d*)").split(expr):
        if not p:
            continue
        if re.match(r"^\d+\.?\d*$", p):
            tokens.append(float(p))
        else:
            for ch in p:
                if ch in OPERACIONES:
                    tokens.append(ch)
    return tokens


def a_notacion_postfija(tokens: list) -> list:
    salida, pila = [], []
    for tok in tokens:
        if isinstance(tok, float):
            salida.append(tok)
        elif tok in OPERACIONES:
            while pila and pila[-1] in OPERACIONES and \
                  PRECEDENCIA[pila[-1]] >= PRECEDENCIA[tok]:
                salida.append(pila.pop())
            pila.append(tok)
    while pila:
        salida.append(pila.pop())
    return salida


def postfija_a_pasos(postfija: list) -> list:
    pila, pasos = [], []
    for tok in postfija:
        if isinstance(tok, float):
            pila.append(tok)
        elif tok in OPERACIONES:
            b = pila.pop()
            a = pila.pop()
            pasos.append((tok, a, b))
            pila.append(None)
    return pasos


# ── Cliente RabbitMQ + gRPC ───────────────────────────────────────────────────

class ClienteOperacion:
    """
    Cada instancia tiene su propia conexión a RabbitMQ.
    Esto es clave para el modo paralelo — si varias peticiones
    compartieran conexión, sus mensajes se mezclarían en las colas.
    """

    def __init__(self, rabbitmq_host: str, grpc_addrs: dict, id_peticion: str):
        self.rabbitmq_host = rabbitmq_host
        self.grpc_addrs    = grpc_addrs
        self.id_peticion   = id_peticion   # para logs identificados
        self._conexion     = None
        self._channel_rmq  = None

    def conectar(self):
        logging.info(f"[{self.id_peticion}] Conectando a RabbitMQ en {self.rabbitmq_host}")
        self._conexion    = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.rabbitmq_host))
        self._channel_rmq = self._conexion.channel()
        self._channel_rmq.exchange_declare(
            exchange=EXCHANGE, exchange_type="direct", durable=True)
        for routing_key, cola in OPERACIONES.values():
            self._channel_rmq.queue_declare(queue=cola, durable=True)
            self._channel_rmq.queue_bind(
                exchange=EXCHANGE, queue=cola, routing_key=routing_key)
        logging.info(f"[{self.id_peticion}] Exchange y colas listos")

    def _llamar_grpc(self, routing_key: str,
                     numeros: calculadora_pb2.Numeros) -> calculadora_pb2.Respuesta:
        """Instancia el stub correcto y llama al método RPC correspondiente."""
        addr  = self.grpc_addrs[routing_key]
        canal = grpc.insecure_channel(addr)
        if routing_key == "add":
            return calculadora_pb2_grpc.SumaServiceStub(canal).Sumar(numeros)
        elif routing_key == "sub":
            return calculadora_pb2_grpc.RestaServiceStub(canal).Restar(numeros)
        elif routing_key == "mul":
            return calculadora_pb2_grpc.MultiplicacionServiceStub(canal).Multiplicar(numeros)
        elif routing_key == "div":
            return calculadora_pb2_grpc.DivisionServiceStub(canal).Dividir(numeros)
        else:
            return calculadora_pb2.Respuesta(error=f"Operación desconocida: {routing_key}")

    def ejecutar(self, operador: str, a: float, b: float) -> calculadora_pb2.Respuesta:
        routing_key, cola = OPERACIONES[operador]

        # 1. Publicar Numeros en la cola con el ID de la petición
        numeros = calculadora_pb2.Numeros(num1=a, num2=b)
        self._channel_rmq.basic_publish(
            exchange=EXCHANGE,
            routing_key=routing_key,
            properties=pika.BasicProperties(
                correlation_id=self.id_peticion,
                content_type="application/protobuf",
                delivery_mode=2,
            ),
            body=numeros.SerializeToString(),
        )
        logging.info(f"[{self.id_peticion}]  → Cola '{cola}': Numeros(num1={a}, num2={b})")

        # 2. Consumir el mensaje de la cola
        method, props, body = self._channel_rmq.basic_get(
            queue=cola, auto_ack=True)
        if body is None:
            return calculadora_pb2.Respuesta(error="Cola vacía")

        numeros_recibido = calculadora_pb2.Numeros.FromString(body)
        logging.info(f"[{self.id_peticion}]  ← Consumido: num1={numeros_recibido.num1}, num2={numeros_recibido.num2}")

        # 3. Llamar al servicio gRPC correcto
        respuesta = self._llamar_grpc(routing_key, numeros_recibido)

        campo = respuesta.WhichOneof("resultado")
        valor = respuesta.data if campo == "data" else respuesta.error
        logging.info(f"[{self.id_peticion}]  ✓ [{self.grpc_addrs[routing_key]}] {campo} = {valor}")
        return respuesta

    def cerrar(self):
        if self._conexion and self._conexion.is_open:
            self._conexion.close()


# ── Servicer gRPC ─────────────────────────────────────────────────────────────

class OrquestadorServicer(calculadora_pb2_grpc.OrquestadorServiceServicer):

    def __init__(self, rabbitmq_host: str, grpc_addrs: dict):
        self.rabbitmq_host = rabbitmq_host
        self.grpc_addrs    = grpc_addrs

    def Calcular(self, request, context):
        expr = request.expr.strip()

        # Usar el ID del cliente o generar uno si no viene
        id_peticion = request.id if request.id else str(uuid.uuid4())[:8]
        logging.info(f"[{id_peticion}] Calcular: '{expr}'")

        try:
            pasos = postfija_a_pasos(a_notacion_postfija(tokenizar(expr)))
            logging.info(f"[{id_peticion}] Pasos: {pasos}")

            # Cada petición tiene su propia conexión a RabbitMQ
            cliente = ClienteOperacion(self.rabbitmq_host, self.grpc_addrs, id_peticion)
            cliente.conectar()

            pila, respuesta_final = [], None
            for operador, a, b in pasos:
                val_a = pila.pop() if a is None else a
                val_b = pila.pop() if b is None else b
                if a is None and b is None:
                    val_b, val_a = val_a, val_b

                logging.info(f"[{id_peticion}] Paso: {val_a} {operador} {val_b}")
                respuesta = cliente.ejecutar(operador, val_a, val_b)

                if respuesta.WhichOneof("resultado") == "error":
                    cliente.cerrar()
                    return calculadora_pb2.Respuesta(
                        error=respuesta.error,
                        id=id_peticion,
                    )

                pila.append(respuesta.data)
                respuesta_final = respuesta

            cliente.cerrar()
            logging.info(f"[{id_peticion}] Resultado: {respuesta_final.data}")

            return calculadora_pb2.Respuesta(
                data=respuesta_final.data,
                id=id_peticion,
            )

        except Exception as e:
            logging.error(f"[{id_peticion}] Error: {e}")
            return calculadora_pb2.Respuesta(error=str(e), id=id_peticion)


# ── Arranque ──────────────────────────────────────────────────────────────────

def serve(port: int, rabbitmq_host: str, grpc_addrs: dict):
    # max_workers=50 permite hasta 50 peticiones simultáneas
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
    calculadora_pb2_grpc.add_OrquestadorServiceServicer_to_server(
        OrquestadorServicer(rabbitmq_host, grpc_addrs), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"OrquestadorService en puerto {port} (max 50 peticiones paralelas)")
    logging.info(f"RabbitMQ: {rabbitmq_host}")
    for k, addr in grpc_addrs.items():
        logging.info(f"  gRPC [{k}] -> {addr}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor gRPC Orquestador")
    parser.add_argument("--port",            type=int, default=50060)
    parser.add_argument("--rabbitmq-host",   type=str, default="localhost")
    parser.add_argument("--grpc-host-suma",  type=str, default="localhost")
    parser.add_argument("--grpc-host-resta", type=str, default="localhost")
    parser.add_argument("--grpc-host-mul",   type=str, default="localhost")
    parser.add_argument("--grpc-host-div",   type=str, default="localhost")
    parser.add_argument("--port-suma",       type=int, default=50051)
    parser.add_argument("--port-resta",      type=int, default=50052)
    parser.add_argument("--port-mul",        type=int, default=50053)
    parser.add_argument("--port-div",        type=int, default=50054)
    args = parser.parse_args()

    grpc_addrs = {
        "add": f"{args.grpc_host_suma}:{args.port_suma}",
        "sub": f"{args.grpc_host_resta}:{args.port_resta}",
        "mul": f"{args.grpc_host_mul}:{args.port_mul}",
        "div": f"{args.grpc_host_div}:{args.port_div}",
    }
    serve(args.port, args.rabbitmq_host, grpc_addrs)
