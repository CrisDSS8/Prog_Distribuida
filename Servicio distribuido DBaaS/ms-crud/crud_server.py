"""
crud_server.py
Punto de entrada del MS5 — CRUD Service.
Recibe IROperation del broker, detecta el modo de la tabla
(normal o colección), traduce a MySQL y ejecuta.
"""

import grpc
import json
import os
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

import ir_to_sql
import executor
from ir_to_sql import IRTranslationError

PORT = os.getenv("CRUD_PORT", "50054")

# Operaciones permitidas por rol
WRITE_OPS = {"insert", "update", "delete"}
READ_OPS  = {"find"}


class CrudServicer(dbaas_pb2_grpc.CrudServiceServicer):

    def Insert(self, request, context):
        if not _check_role(request.role, "insert"):
            return _crud_error(f"Rol '{request.role}' sin permiso para insertar")
        return self._run(request, "insert")

    def Find(self, request, context):
        return self._run(request, "find")

    def Update(self, request, context):
        if not _check_role(request.role, "update"):
            return _crud_error(f"Rol '{request.role}' sin permiso para actualizar")
        return self._run(request, "update")

    def Delete(self, request, context):
        if not _check_role(request.role, "delete"):
            return _crud_error(f"Rol '{request.role}' sin permiso para eliminar")
        return self._run(request, "delete")

    def _run(self, request, op: str):
        """
        Flujo común para todas las operaciones:
          1. Construir dict IR desde el request
          2. Detectar si la tabla es colección
          3. Traducir IR a query MySQL
          4. Ejecutar y retornar resultado
        """
        ir = {
            "operation": op,
            "database":  request.database,
            "table":     request.table,
            "fields":    request.fields  or '["*"]',
            "filter":    request.filter  or "{}",
            "data":      request.data    or "{}",
            "options":   request.options or "{}",
        }

        database = ir["database"]
        table    = ir["table"]

        if not database or not table:
            return _crud_error("Base de datos o tabla no especificada")

        try:
            # detectar modo de la tabla
            col_mode = executor.is_collection(database, table)

            # traducir IR a query MySQL
            query, params = ir_to_sql.translate(ir, collection_mode=col_mode)

            # ejecutar según operación
            if op == "insert":
                result = executor.run_insert(database, query, params)
                return dbaas_pb2.CrudResponse(
                    success       = result["success"],
                    message       = result["message"],
                    affected_rows = result.get("affected_rows", 0),
                )

            if op == "find":
                fields = json.loads(ir["fields"])
                result = executor.run_find(database, query, params, col_mode, fields)
                docs   = [json.dumps(d, default=str) for d in result["documents"]]
                return dbaas_pb2.FindResponse(
                    success   = result["success"],
                    message   = result["message"],
                    documents = docs,
                )

            # update / delete
            result = executor.run_write(database, query, params, op)
            return dbaas_pb2.CrudResponse(
                success       = result["success"],
                message       = result["message"],
                affected_rows = result.get("affected_rows", 0),
            )

        except IRTranslationError as e:
            return _crud_error(f"Error de traducción: {str(e)}")
        except Exception as e:
            return _crud_error(f"Error interno: {str(e)}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_role(role: str, op: str) -> bool:
    if op in WRITE_OPS:
        return role in ("admin", "write")
    return True


def _crud_error(msg: str):
    """Retorna el tipo de error correcto según la operación."""
    return dbaas_pb2.CrudResponse(success=False, message=msg, affected_rows=0)


# ── Servidor ──────────────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbaas_pb2_grpc.add_CrudServiceServicer_to_server(CrudServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[crud] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
