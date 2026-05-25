"""
gateway_client.py
Abstrae toda comunicación gRPC con el Gateway.
El resto del cliente solo llama métodos de esta clase.
"""

import grpc
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

GATEWAY_ADDR = os.getenv("GATEWAY_ADDR", "localhost:50051")


class GatewayClient:

    def __init__(self):
        self.channel = grpc.insecure_channel(GATEWAY_ADDR)
        self.stub    = dbaas_pb2_grpc.GatewayServiceStub(self.channel)

    # -- Auth

    def login(self, username: str, password: str) -> dict:
        try:
            r = self.stub.Login(dbaas_pb2.LoginRequest(
                username=username, password=password
            ))
            return {
                "success": r.success,
                "token":   r.token,
                "role":    r.role,       # el gateway incluye el rol en la respuesta
                "message": r.message,
            }
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error de conexión: {e.details()}"}

    def register(self, username: str, password: str, role: str) -> dict:
        try:
            r = self.stub.Register(dbaas_pb2.RegisterRequest(
                username=username, password=password, role=role
            ))
            return {"success": r.success, "message": r.message}
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error de conexión: {e.details()}"}

    # -- SQL

    def send_sql(self, query: str, active_db: str, session: dict) -> dict:
        """
        Manda una query SQL al Gateway.
        El Gateway la reenvía al broker con interface='sql'.
        """
        try:
            r = self.stub.Execute(dbaas_pb2.ExecuteRequest(
                interface  = "sql",
                payload    = query,
                active_db  = active_db or "",
                token      = session["token"],
            ))
            return json.loads(r.data) | {"success": r.success, "message": r.message}
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error de conexión: {e.details()}"}

    # -- NoSQL

    def send_nosql(self, msg: dict, session: dict) -> dict:
        """
        Serializa el dict a JSON y lo manda al Gateway.
        El Gateway lo reenvía al broker con interface='nosql'.
        """
        try:
            r = self.stub.Execute(dbaas_pb2.ExecuteRequest(
                interface  = "nosql",
                payload    = json.dumps(msg),
                active_db  = msg.get("db", ""),
                token      = session["token"],
            ))
            return json.loads(r.data) | {"success": r.success, "message": r.message}
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error de conexión: {e.details()}"}
