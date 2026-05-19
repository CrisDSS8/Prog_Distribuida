"""
broker_server.py
Punto de entrada del MS2 — Translation Broker.
Expone un servicio gRPC al Gateway, recibe el mensaje crudo del cliente
(SQL string o JSON dict), lo parsea y lo enruta al servicio correcto.
"""

import grpc
import json
import sys
import os
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

from parsers import sql_parser, nosql_parser
from parsers.sql_parser import SQLParseError
from parsers.nosql_parser import NoSQLParseError
from router import route

PORT = os.getenv("BROKER_PORT", "50052")


class BrokerService(dbaas_pb2_grpc.BrokerServiceServicer):
    """
    Recibe del Gateway un BrokerRequest con:
      - interface : "sql" | "nosql"
      - payload   : string con la query SQL o JSON serializado
      - role      : rol del usuario (ya validado por el Gateway)
      - user_id   : id del usuario autenticado
    """

    def Process(self, request, context):
        try:
            ir = _parse(request.interface, request.payload)
            result = route(ir, request.role, request.user_id)
            return dbaas_pb2.BrokerResponse(
                success=result.get("success", False),
                message=result.get("message", ""),
                data=json.dumps(result),
            )

        except (SQLParseError, NoSQLParseError) as e:
            return dbaas_pb2.BrokerResponse(
                success=False,
                message=f"Error de parseo: {str(e)}",
                data="{}",
            )
        except Exception as e:
            return dbaas_pb2.BrokerResponse(
                success=False,
                message=f"Error interno del broker: {str(e)}",
                data="{}",
            )


def _parse(interface: str, payload: str) -> dict:
    if interface == "sql":
        return sql_parser.parse(payload)

    if interface == "nosql":
        try:
            msg = json.loads(payload)
        except json.JSONDecodeError:
            raise NoSQLParseError("El payload NoSQL no es JSON válido")
        return nosql_parser.parse(msg)

    raise ValueError(f"Interfaz desconocida: {interface}")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbaas_pb2_grpc.add_BrokerServiceServicer_to_server(BrokerService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[broker] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
