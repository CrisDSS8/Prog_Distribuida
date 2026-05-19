"""
router.py
Recibe el dict IR ya construido por cualquiera de los dos parsers
y lo despacha al microservicio correcto vía gRPC.
"""

import grpc
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

# Direcciones de cada microservicio (pueden venir de variables de entorno)
ADMIN_ADDR = os.getenv("ADMIN_ADDR", "localhost:50053")
CRUD_ADDR  = os.getenv("CRUD_ADDR",  "localhost:50054")
QUERY_ADDR = os.getenv("QUERY_ADDR", "localhost:50055")

# Tabla de ruteo: qué operaciones van a qué servicio
ADMIN_OPS = {"create_db", "drop_db", "list_dbs",
             "create_table", "drop_table", "list_tables"}
CRUD_OPS  = {"insert", "find", "update", "delete"}
QUERY_OPS = {"count", "sum", "avg", "distinct", "join"}


def route(ir: dict, role: str, user_id: str) -> dict:
    """
    Parámetros:
        ir      : dict producido por sql_parser o nosql_parser
        role    : rol extraído del JWT ("admin" | "write" | "read")
        user_id : id del usuario autenticado

    Retorna:
        dict con 'success', 'message', y datos opcionales según la operación
    """
    op = ir.get("operation", "")

    if op in ADMIN_OPS:
        return _route_admin(ir, role, user_id)
    if op in CRUD_OPS:
        return _route_crud(ir, role, user_id)
    if op in QUERY_OPS:
        return _route_query(ir, role, user_id)

    return {"success": False, "message": f"Operación desconocida: {op}"}


# ── ADMIN ─────────────────────────────────────────────────────────────────────

def _route_admin(ir: dict, role: str, user_id: str):
    op = ir["operation"]
    channel = grpc.insecure_channel(ADMIN_ADDR)
    stub    = dbaas_pb2_grpc.AdminServiceStub(channel)

    if op == "create_db":
        r = stub.CreateDatabase(dbaas_pb2.DatabaseRequest(
            database=ir.get("database", ""), role=role, user_id=user_id
        ))
        return {"success": r.success, "message": r.message}

    if op == "drop_db":
        r = stub.DropDatabase(dbaas_pb2.DatabaseRequest(
            database=ir.get("database", ""), role=role, user_id=user_id
        ))
        return {"success": r.success, "message": r.message}

    if op == "list_dbs":
        r = stub.ListDatabases(dbaas_pb2.ListDbRequest(role=role, user_id=user_id))
        return {"success": r.success, "databases": list(r.databases)}

    if op == "create_table":
        opts = json.loads(ir.get("options", "{}"))
        r = stub.CreateTable(dbaas_pb2.CreateTableRequest(
            database=ir.get("database", ""),
            table=ir.get("table", ""),
            mode=opts.get("mode", "collection"),
            schema=json.dumps(opts.get("schema", [])),
            role=role,
            user_id=user_id,
        ))
        return {"success": r.success, "message": r.message}

    if op == "drop_table":
        r = stub.DropTable(dbaas_pb2.TableRequest(
            database=ir.get("database", ""),
            table=ir.get("table", ""),
            role=role,
            user_id=user_id,
        ))
        return {"success": r.success, "message": r.message}

    if op == "list_tables":
        r = stub.ListTables(dbaas_pb2.TableRequest(
            database=ir.get("database", ""),
            table="",
            role=role,
            user_id=user_id,
        ))
        return {"success": r.success, "tables": list(r.tables)}


# ── CRUD ──────────────────────────────────────────────────────────────────────

def _route_crud(ir: dict, role: str, user_id: str):
    op  = ir["operation"]
    msg = _build_ir_proto(ir, role, user_id)

    channel = grpc.insecure_channel(CRUD_ADDR)
    stub    = dbaas_pb2_grpc.CrudServiceStub(channel)

    handlers = {
        "insert": stub.Insert,
        "find":   stub.Find,
        "update": stub.Update,
        "delete": stub.Delete,
    }

    r = handlers[op](msg)

    if op == "find":
        return {
            "success":   r.success,
            "message":   r.message,
            "documents": [json.loads(d) for d in r.documents],
        }

    return {"success": r.success, "message": r.message, "affected_rows": r.affected_rows}


# ── QUERY ─────────────────────────────────────────────────────────────────────

def _route_query(ir: dict, role: str, user_id: str):
    op  = ir["operation"]
    msg = _build_ir_proto(ir, role, user_id)

    channel = grpc.insecure_channel(QUERY_ADDR)
    stub    = dbaas_pb2_grpc.QueryServiceStub(channel)

    scalar_handlers = {
        "count": stub.Count,
        "sum":   stub.Sum,
        "avg":   stub.Avg,
    }

    if op in scalar_handlers:
        r = scalar_handlers[op](msg)
        return {"success": r.success, "message": r.message, "value": r.value}

    if op == "distinct":
        r = stub.Distinct(msg)
        return {"success": r.success, "message": r.message, "values": list(r.values)}

    if op == "join":
        r = stub.Join(msg)
        return {
            "success":   r.success,
            "message":   r.message,
            "documents": [json.loads(d) for d in r.documents],
        }


# ── HELPER ────────────────────────────────────────────────────────────────────

def _build_ir_proto(ir: dict, role: str, user_id: str) -> dbaas_pb2.IROperation:
    return dbaas_pb2.IROperation(
        operation=ir.get("operation", ""),
        database=ir.get("database", ""),
        table=ir.get("table", ""),
        fields=ir.get("fields", "[]"),
        filter=ir.get("filter", "{}"),
        data=ir.get("data", "{}"),
        options=ir.get("options", "{}"),
        role=role,
        user_id=user_id,
    )
