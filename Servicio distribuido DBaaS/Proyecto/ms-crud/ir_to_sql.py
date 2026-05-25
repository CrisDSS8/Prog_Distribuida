"""
ir_to_sql.py
Traduce el dict IR a queries MySQL ejecutables.
Es el puente final entre la representación interna y el motor de base de datos.

Detecta automáticamente si la tabla es una colección (modo JSON)
o una tabla normal, y genera la query correspondiente.
"""

import json
import uuid


class IRTranslationError(Exception):
    pass


# ── Punto de entrada ──────────────────────────────────────────────────────────

def translate(ir: dict, collection_mode: bool = False) -> tuple[str, list]:
    """
    Parámetros:
        ir              : dict con los campos de IROperation
        collection_mode : True si la tabla es una colección JSON

    Retorna:
        (query_string, params)
        Los params van separados para usar prepared statements y evitar SQL injection.
    """
    op = ir.get("operation", "")

    translators = {
        "insert": _insert,
        "find":   _find,
        "update": _update,
        "delete": _delete,
    }

    if op not in translators:
        raise IRTranslationError(f"Operación CRUD desconocida: {op}")

    return translators[op](ir, collection_mode)


# ── INSERT ────────────────────────────────────────────────────────────────────

def _insert(ir: dict, collection_mode: bool) -> tuple[str, list]:
    table = ir["table"]
    data  = json.loads(ir.get("data", "{}"))

    if not data:
        raise IRTranslationError("No hay datos para insertar")

    if collection_mode:
        # colección: guardamos el documento completo en _data como JSON
        doc_id = str(uuid.uuid4())
        query  = f"INSERT INTO `{table}` (_id, _data) VALUES (%s, %s)"
        params = [doc_id, json.dumps(data)]
    else:
        # tabla normal: columnas explícitas
        columns = ", ".join(f"`{c}`" for c in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query  = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"
        params = list(data.values())

    return query, params


# ── FIND ──────────────────────────────────────────────────────────────────────

def _find(ir: dict, collection_mode: bool) -> tuple[str, list]:
    table  = ir["table"]
    fields = json.loads(ir.get("fields", '["*"]'))
    filt   = json.loads(ir.get("filter", "{}"))
    opts   = json.loads(ir.get("options", "{}"))

    if collection_mode:
        # seleccionar siempre _id y _data; los campos se filtran en Python después
        select = "SELECT _id, _data"
    else:
        if fields == ["*"] or not fields:
            select = "SELECT *"
        else:
            select = "SELECT " + ", ".join(f"`{f}`" for f in fields)

    where, params = _build_where(filt, collection_mode)
    limit = f" LIMIT {opts['limit']}" if "limit" in opts else ""

    query = f"{select} FROM `{table}`{where}{limit}"
    return query, params


# ── UPDATE ────────────────────────────────────────────────────────────────────

def _update(ir: dict, collection_mode: bool) -> tuple[str, list]:
    table = ir["table"]
    data  = json.loads(ir.get("data",   "{}"))
    filt  = json.loads(ir.get("filter", "{}"))

    if not data:
        raise IRTranslationError("No hay datos para actualizar")
    if not filt:
        raise IRTranslationError("UPDATE sin filtro denegaría actualizar toda la tabla")

    if collection_mode:
        # actualizar campos dentro del JSON usando JSON_SET
        set_parts  = []
        set_params = []
        for key, val in data.items():
            set_parts.append(f"_data = JSON_SET(_data, '$.{key}', %s)")
            set_params.append(val)
        set_clause = ", ".join(set_parts)
    else:
        set_parts  = [f"`{k}` = %s" for k in data.keys()]
        set_params = list(data.values())
        set_clause = ", ".join(set_parts)

    where, where_params = _build_where(filt, collection_mode)
    query  = f"UPDATE `{table}` SET {set_clause}{where}"
    params = set_params + where_params

    return query, params


# ── DELETE ────────────────────────────────────────────────────────────────────

def _delete(ir: dict, collection_mode: bool) -> tuple[str, list]:
    table = ir["table"]
    filt  = json.loads(ir.get("filter", "{}"))

    if not filt:
        raise IRTranslationError("DELETE sin filtro denegaría eliminar toda la tabla")

    where, params = _build_where(filt, collection_mode)
    query = f"DELETE FROM `{table}`{where}"
    return query, params


# ── WHERE builder ─────────────────────────────────────────────────────────────

# Mapeo de operadores IR → SQL
OP_MAP = {
    "$eq":  "=",
    "$ne":  "!=",
    "$gt":  ">",
    "$gte": ">=",
    "$lt":  "<",
    "$lte": "<=",
}


def _build_where(filt: dict, collection_mode: bool) -> tuple[str, list]:
    """
    Convierte el filtro IR a una cláusula WHERE MySQL.

    Modo tabla:     {"edad": {"$gt": 18}}  →  WHERE `edad` > %s       params=[18]
    Modo colección: {"edad": {"$gt": 18}}  →  WHERE JSON_EXTRACT(_data,'$.edad') > %s
    """
    if not filt:
        return "", []

    conditions = []
    params     = []

    for field, condition in filt.items():
        if isinstance(condition, dict):
            for op, val in condition.items():
                sql_op = OP_MAP.get(op)
                if not sql_op:
                    raise IRTranslationError(f"Operador no soportado: {op}")
                col = _col_ref(field, collection_mode)
                conditions.append(f"{col} {sql_op} %s")
                params.append(val)
        else:
            # {"campo": valor}  →  campo = valor  (shorthand para $eq)
            col = _col_ref(field, collection_mode)
            conditions.append(f"{col} = %s")
            params.append(condition)

    where = " WHERE " + " AND ".join(conditions)
    return where, params


def _col_ref(field: str, collection_mode: bool) -> str:
    """Referencia a un campo según el modo de almacenamiento."""
    if collection_mode:
        return f"JSON_EXTRACT(_data, '$.{field}')"
    return f"`{field}`"
