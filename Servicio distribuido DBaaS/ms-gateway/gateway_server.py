"""
gateway_server.py
Punto de entrada del MS1 — API Gateway.
Es el único servicio que el cliente conoce.
Responsabilidades:
  1. Exponer Login y Register (los pasa directo al Auth Service)
  2. Validar JWT en cada petición Execute
  3. Verificar permisos por rol antes de reenviar
  4. Reenviar la petición al Translation Broker
  5. Publicar evento en RabbitMQ después de cada operación (async)
"""

import grpc
import json
import os
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

import role_guard

# ── Direcciones de servicios ──────────────────────────────────────────────────
AUTH_ADDR   = os.getenv("AUTH_ADDR",   "localhost:50056")
BROKER_ADDR = os.getenv("BROKER_ADDR", "localhost:50052")
PORT        = os.getenv("GATEWAY_PORT", "50051")

# ── RabbitMQ (importación opcional: si falla no detiene el gateway) ────────────
try:
    import pika
    RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBIT_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBIT_USER = os.getenv("RABBITMQ_USER", "admin")
    RABBIT_PASS = os.getenv("RABBITMQ_PASS", "admin1234")
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False
    print("[gateway] pika no disponible, eventos async desactivados")


class GatewayServicer(dbaas_pb2_grpc.GatewayServiceServicer):

    def __init__(self):
        # canales gRPC reutilizables
        self._auth_channel   = grpc.insecure_channel(AUTH_ADDR)
        self._broker_channel = grpc.insecure_channel(BROKER_ADDR)
        self._auth_stub      = dbaas_pb2_grpc.AuthServiceStub(self._auth_channel)
        self._broker_stub    = dbaas_pb2_grpc.BrokerServiceStub(self._broker_channel)

    # ── Login ─────────────────────────────────────────────────────────────────

    def Login(self, request, context):
        """
        Pasa las credenciales al Auth Service y devuelve el JWT + rol al cliente.
        El rol se extrae del JWT para incluirlo en la respuesta sin que el
        cliente tenga que decodificar el token por su cuenta.
        """
        try:
            r = self._auth_stub.Login(dbaas_pb2.LoginRequest(
                username=request.username,
                password=request.password,
            ))

            if not r.success:
                return dbaas_pb2.GatewayAuthResponse(
                    success=False, token="", role="", message=r.message
                )

            # validar el token recién emitido para extraer el rol
            payload = self._auth_stub.ValidateToken(
                dbaas_pb2.TokenRequest(token=r.token)
            )

            return dbaas_pb2.GatewayAuthResponse(
                success=True,
                token=r.token,
                role=payload.role,
                message="Login exitoso",
            )

        except grpc.RpcError as e:
            return dbaas_pb2.GatewayAuthResponse(
                success=False, token="", role="",
                message=f"Auth Service no disponible: {e.details()}"
            )

    # ── Register ──────────────────────────────────────────────────────────────

    def Register(self, request, context):
        """
        Solo un admin puede registrar a otro admin.
        Para registros sin token (primer usuario del sistema) se permite
        únicamente rol 'read' o 'write'.
        """
        try:
            r = self._auth_stub.Register(dbaas_pb2.RegisterRequest(
                username=request.username,
                password=request.password,
                role=request.role,
            ))
            return dbaas_pb2.GatewayAuthResponse(
                success=r.success, token="", role="", message=r.message
            )
        except grpc.RpcError as e:
            return dbaas_pb2.GatewayAuthResponse(
                success=False, token="", role="",
                message=f"Auth Service no disponible: {e.details()}"
            )

    # ── Execute ───────────────────────────────────────────────────────────────

    def Execute(self, request, context):
        """
        Flujo:
          1. Validar JWT → obtener rol y user_id
          2. Detectar la operación (para verificar permisos)
          3. Verificar que el rol permite la operación
          4. Reenviar al broker
          5. Publicar evento async en RabbitMQ
        """

        # ── 1. Validar JWT ────────────────────────────────────────────────────
        try:
            payload = self._auth_stub.ValidateToken(
                dbaas_pb2.TokenRequest(token=request.token)
            )
        except grpc.RpcError as e:
            return _error(f"Auth Service no disponible: {e.details()}")

        if not payload.valid:
            return _error(f"Token inválido: {payload.message}")

        role    = payload.role
        user_id = payload.user_id

        # ── 2. Detectar operación para verificar permisos ─────────────────────
        operation = _detect_operation(request.interface, request.payload)
        if not operation:
            return _error("No se pudo detectar la operación de la petición")

        # ── 3. Verificar permisos ─────────────────────────────────────────────
        if not role_guard.is_allowed(role, operation):
            return _error(role_guard.denial_message(role, operation))

        # ── 4. Reenviar al broker ─────────────────────────────────────────────
        try:
            # inyectar la base de datos activa en el payload SQL si falta
            payload_final = _inject_db(request.interface, request.payload, request.active_db)

            r = self._broker_stub.Process(dbaas_pb2.BrokerRequest(
                interface=request.interface,
                payload=payload_final,
                role=role,
                user_id=user_id,
            ))
        except grpc.RpcError as e:
            return _error(f"Broker no disponible: {e.details()}")

        # ── 5. Evento async en RabbitMQ ───────────────────────────────────────
        _publish_event({
            "user_id":   user_id,
            "role":      role,
            "operation": operation,
            "interface": request.interface,
            "success":   r.success,
        })

        return dbaas_pb2.ExecuteResponse(
            success=r.success,
            message=r.message,
            data=r.data,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(msg: str) -> dbaas_pb2.ExecuteResponse:
    return dbaas_pb2.ExecuteResponse(success=False, message=msg, data="{}")


def _detect_operation(interface: str, payload: str) -> str | None:
    """
    Extrae el nombre de la operación del payload sin hacer un parse completo.
    Solo necesitamos saber la operación para verificar permisos.
    """
    try:
        if interface == "nosql":
            return json.loads(payload).get("op", "").lower()

        # SQL: detectar por la primera palabra
        first = payload.strip().split()[0].upper()
        mapping = {
            "SELECT": "find",
            "INSERT": "insert",
            "UPDATE": "update",
            "DELETE": "delete",
            "CREATE": _detect_create(payload),
            "DROP":   _detect_drop(payload),
            "SHOW":   "list_dbs",
        }
        return mapping.get(first)
    except Exception:
        return None


def _detect_create(sql: str) -> str:
    words = sql.upper().split()
    if len(words) > 1:
        if words[1] == "DATABASE":
            return "create_db"
        if words[1] in ("TABLE", "COLLECTION"):
            return "create_table"
    return "create_table"


def _detect_drop(sql: str) -> str:
    words = sql.upper().split()
    if len(words) > 1 and words[1] == "DATABASE":
        return "drop_db"
    return "drop_table"


def _inject_db(interface: str, payload: str, active_db: str) -> str:
    """
    Si el cliente tiene una base de datos activa (USE mi_db en SQL),
    la inyecta en el payload para que el broker la tenga disponible.
    Solo aplica a SQL, en NoSQL el campo 'db' ya viene en el mensaje.
    """
    if interface != "sql" or not active_db:
        return payload

    # Se agrega como prefijo especial que el broker inyecta en la IR
    # Formato: "USE active_db;\n<query original>"
    if not payload.strip().upper().startswith("USE "):
        return f"USE {active_db};\n{payload}"

    return payload


def _publish_event(event: dict):
    """
    Publica un evento de auditoría en RabbitMQ de forma no bloqueante.
    Si RabbitMQ no está disponible, solo loguea y continúa.
    """
    if not RABBITMQ_AVAILABLE:
        return

    try:
        credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
        params      = pika.ConnectionParameters(
            host=RABBIT_HOST, port=RABBIT_PORT,
            credentials=credentials,
            connection_attempts=1,
            socket_timeout=2,           # timeout corto para no bloquear
        )
        connection = pika.BlockingConnection(params)
        channel    = connection.channel()
        channel.queue_declare(queue="dbaas.audit", durable=True)
        channel.basic_publish(
            exchange="",
            routing_key="dbaas.audit",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),  # mensaje persistente
        )
        connection.close()
    except Exception as e:
        # el evento perdido no debe detener la respuesta al cliente
        print(f"[gateway] warning: no se pudo publicar evento en RabbitMQ: {e}")


# ── Servidor ──────────────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    dbaas_pb2_grpc.add_GatewayServiceServicer_to_server(GatewayServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[gateway] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
