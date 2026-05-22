"""
auth_server.py
Punto de entrada del MS3 — Auth Service.
Expone tres RPCs: Register, Login, ValidateToken.
"""

import grpc
import os
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

import jwt_handler
import user_store

PORT = os.getenv("AUTH_PORT", "50056")


class AuthServicer(dbaas_pb2_grpc.AuthServiceServicer):

    # ── Register ──────────────────────────────────────────────────────────────

    def Register(self, request, context):
        """
        Registra un nuevo usuario.
        Solo un admin debería poder crear otros admins,
        pero esa validación la hace el Gateway antes de llegar aquí.
        """
        result = user_store.create_user(
            request.username,
            request.password,
            request.role or "read",
        )
        return dbaas_pb2.AuthResponse(
            success = result["success"],
            token   = "",               # no emitimos token en registro, el usuario debe hacer login
            message = result["message"],
        )

    # ── Login ─────────────────────────────────────────────────────────────────

    def Login(self, request, context):
        """
        Verifica credenciales y emite JWT si son correctas.
        """
        result = user_store.verify_user(request.username, request.password)

        if not result["success"]:
            return dbaas_pb2.AuthResponse(
                success = False,
                token   = "",
                message = result["message"],
            )

        token = jwt_handler.generate(
            user_id  = result["user_id"],
            username = request.username,
            role     = result["role"],
        )

        return dbaas_pb2.AuthResponse(
            success = True,
            token   = token,
            message = "Login exitoso",
        )

    # ── ValidateToken ─────────────────────────────────────────────────────────

    def ValidateToken(self, request, context):
        """
        El Gateway llama aquí en cada petición para verificar el JWT.
        Retorna el payload decodificado si el token es válido.
        """
        result = jwt_handler.validate(request.token)

        if not result["valid"]:
            return dbaas_pb2.TokenPayload(
                valid   = False,
                message = result["message"],
            )

        return dbaas_pb2.TokenPayload(
            valid    = True,
            user_id  = result["user_id"],
            username = result["username"],
            role     = result["role"],
            message  = "Token válido",
        )


def serve():
    user_store.init()       # crea DB y tabla si no existen
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbaas_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[auth] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
