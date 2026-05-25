"""
admin_server.py
Punto de entrada del MS4 — Admin Service.
Recibe IROperation del broker y delega en db_manager.
Valida que el rol sea 'admin' antes de cualquier operación destructiva.
"""

import grpc
import json
import os
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

import db_manager

PORT = os.getenv("ADMIN_PORT", "50053")

# Operaciones que solo el rol admin puede ejecutar
ADMIN_ONLY = {"create_db", "drop_db", "create_table", "drop_table"}


class AdminServicer(dbaas_pb2_grpc.AdminServiceServicer):

    # ── Bases de datos ────────────────────────────────────────────────────────

    def CreateDatabase(self, request, context):
        if not _check_role(request.role, "create_db"):
            return _status(False, f"Rol '{request.role}' sin permiso para crear bases de datos")
        result = db_manager.create_database(request.database)
        return _status(result["success"], result["message"])

    def DropDatabase(self, request, context):
        if not _check_role(request.role, "drop_db"):
            return _status(False, f"Rol '{request.role}' sin permiso para eliminar bases de datos")
        result = db_manager.drop_database(request.database)
        return _status(result["success"], result["message"])

    def ListDatabases(self, request, context):
        result = db_manager.list_databases()
        return dbaas_pb2.ListDbResponse(
            success   = result["success"],
            databases = result.get("databases", []),
        )

    # ── Tablas / colecciones ──────────────────────────────────────────────────

    def CreateTable(self, request, context):
        if not _check_role(request.role, "create_table"):
            return _status(False, f"Rol '{request.role}' sin permiso para crear tablas")

        # el schema viene como JSON string desde el broker
        try:
            schema = json.loads(request.schema) if request.schema else []
        except json.JSONDecodeError:
            schema = []

        result = db_manager.create_table(
            database = request.database,
            table    = request.table,
            mode     = request.mode or "collection",
            schema   = schema,
        )
        return _status(result["success"], result["message"])

    def DropTable(self, request, context):
        if not _check_role(request.role, "drop_table"):
            return _status(False, f"Rol '{request.role}' sin permiso para eliminar tablas")
        result = db_manager.drop_table(request.database, request.table)
        return _status(result["success"], result["message"])

    def ListTables(self, request, context):
        result = db_manager.list_tables(request.database)
        return dbaas_pb2.ListTablesResponse(
            success = result["success"],
            tables  = result.get("tables", []),
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_role(role: str, operation: str) -> bool:
    """Segunda línea de defensa: el Gateway ya validó, pero el servicio vuelve a verificar."""
    if operation in ADMIN_ONLY:
        return role == "admin"
    return True  # list_dbs y list_tables las puede hacer cualquier rol


def _status(success: bool, message: str) -> dbaas_pb2.StatusResponse:
    return dbaas_pb2.StatusResponse(success=success, message=message)


# ── Servidor ──────────────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbaas_pb2_grpc.add_AdminServiceServicer_to_server(AdminServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[admin] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
