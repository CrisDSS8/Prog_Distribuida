"""
nosql_parser.py
Recibe un dict Python (ya deserializado desde JSON del cliente)
con sintaxis inspirada en MongoDB y produce el mismo dict IR que sql_parser.
"""

import json


class NoSQLParseError(Exception):
    pass


# Operaciones que el cliente puede enviar en el campo "op"
VALID_OPS = {
    "find", "insert", "update", "delete",
    "create_db", "drop_db", "list_dbs",
    "create_table", "drop_table", "list_tables",
    "count", "sum", "avg", "distinct", "join",
}


def parse(message: dict) -> dict:
    """
    Entrada : dict del cliente (ya parseado desde JSON)
    Salida  : dict IR igual al que produce sql_parser

    Ejemplo de entrada:
    {
      "op":         "find",
      "db":         "tienda",
      "collection": "productos",
      "filter":     {"precio": {"$gt": 100}},
      "fields":     ["nombre", "precio"],
      "options":    {"limit": 10}
    }
    """
    op = message.get("op", "").lower()

    if not op:
        raise NoSQLParseError("El mensaje JSON no tiene campo 'op'")
    if op not in VALID_OPS:
        raise NoSQLParseError(f"Operación no reconocida: {op}")

    parsers = {
        # CRUD
        "find":         _parse_find,
        "insert":       _parse_insert,
        "update":       _parse_update,
        "delete":       _parse_delete,
        # Admin - bases de datos
        "create_db":    _parse_create_db,
        "drop_db":      _parse_drop_db,
        "list_dbs":     _parse_list_dbs,
        # Admin - tablas / colecciones
        "create_table": _parse_create_table,
        "drop_table":   _parse_drop_table,
        "list_tables":  _parse_list_tables,
        # Agregaciones
        "count":        _parse_aggregation,
        "sum":          _parse_aggregation,
        "avg":          _parse_aggregation,
        "distinct":     _parse_distinct,
        "join":         _parse_join,
    }

    return parsers[op](message)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def _parse_find(msg: dict) -> dict:
    return {
        "operation": "find",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "fields":    json.dumps(msg.get("fields", ["*"])),
        "filter":    json.dumps(msg.get("filter", {})),
        "options":   json.dumps(msg.get("options", {})),
    }


def _parse_insert(msg: dict) -> dict:
    if "document" not in msg:
        raise NoSQLParseError("insert requiere campo 'document'")
    return {
        "operation": "insert",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "data":      json.dumps(msg["document"]),
        "filter":    json.dumps({}),
        "options":   json.dumps({}),
    }


def _parse_update(msg: dict) -> dict:
    if "filter" not in msg or "update" not in msg:
        raise NoSQLParseError("update requiere campos 'filter' y 'update'")
    return {
        "operation": "update",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "data":      json.dumps(msg["update"]),
        "filter":    json.dumps(msg["filter"]),
        "options":   json.dumps({}),
    }


def _parse_delete(msg: dict) -> dict:
    if "filter" not in msg:
        raise NoSQLParseError("delete requiere campo 'filter'")
    return {
        "operation": "delete",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "filter":    json.dumps(msg["filter"]),
        "options":   json.dumps({}),
    }


# ── ADMIN — bases de datos ────────────────────────────────────────────────────

def _parse_create_db(msg: dict) -> dict:
    _require(msg, "db")
    return {"operation": "create_db", "database": msg["db"]}


def _parse_drop_db(msg: dict) -> dict:
    _require(msg, "db")
    return {"operation": "drop_db", "database": msg["db"]}


def _parse_list_dbs(msg: dict) -> dict:
    return {"operation": "list_dbs"}


# ── ADMIN — tablas / colecciones ──────────────────────────────────────────────

def _parse_create_table(msg: dict) -> dict:
    _require(msg, "collection")
    mode   = msg.get("mode", "collection")   # "table" | "collection"
    schema = msg.get("schema", [])           # lista de {column, type}, vacío si colección
    return {
        "operation": "create_table",
        "database":  msg.get("db", ""),
        "table":     msg["collection"],
        "options":   json.dumps({"mode": mode, "schema": schema}),
    }


def _parse_drop_table(msg: dict) -> dict:
    _require(msg, "collection")
    return {
        "operation": "drop_table",
        "database":  msg.get("db", ""),
        "table":     msg["collection"],
    }


def _parse_list_tables(msg: dict) -> dict:
    return {
        "operation": "list_tables",
        "database":  msg.get("db", ""),
    }


# ── AGREGACIONES ──────────────────────────────────────────────────────────────

def _parse_aggregation(msg: dict) -> dict:
    """
    COUNT, SUM, AVG — todos tienen la misma estructura de entrada:
    {
      "op":     "sum",
      "db":     "tienda",
      "collection": "ventas",
      "field":  "total",
      "filter": {"activo": {"$eq": true}}
    }
    """
    _require(msg, "field")
    return {
        "operation": msg["op"],
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "fields":    json.dumps([msg["field"]]),
        "filter":    json.dumps(msg.get("filter", {})),
        "options":   json.dumps({}),
    }


def _parse_distinct(msg: dict) -> dict:
    _require(msg, "field")
    return {
        "operation": "distinct",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "fields":    json.dumps([msg["field"]]),
        "filter":    json.dumps(msg.get("filter", {})),
        "options":   json.dumps({}),
    }


def _parse_join(msg: dict) -> dict:
    """
    {
      "op":          "join",
      "db":          "tienda",
      "collection":  "pedidos",
      "join_collection": "clientes",
      "on":          "pedidos.cliente_id = clientes.id",
      "filter":      {},
      "fields":      ["*"]
    }
    """
    _require(msg, "join_collection")
    _require(msg, "on")
    return {
        "operation": "join",
        "database":  msg.get("db", ""),
        "table":     _collection(msg),
        "fields":    json.dumps(msg.get("fields", ["*"])),
        "filter":    json.dumps(msg.get("filter", {})),
        "options":   json.dumps({
            "join_table": msg["join_collection"],
            "on":         msg["on"],
        }),
    }


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _collection(msg: dict) -> str:
    """Acepta 'collection' o 'table' como nombre del recurso."""
    name = msg.get("collection") or msg.get("table", "")
    if not name:
        raise NoSQLParseError("El mensaje debe incluir 'collection' o 'table'")
    return name


def _require(msg: dict, field: str):
    if field not in msg or not msg[field]:
        raise NoSQLParseError(f"Campo requerido ausente: '{field}'")
