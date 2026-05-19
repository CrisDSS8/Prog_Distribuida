"""
sql_parser.py
Recibe una string con sintaxis MySQL y produce un dict con los campos de IROperation.
No ejecuta nada contra la base de datos, solo interpreta la intención del usuario.
"""

import re
import json


class SQLParseError(Exception):
    pass


def parse(sql: str) -> dict:
    """
    Entrada : string SQL  →  "SELECT nombre FROM users WHERE edad > 18"
    Salida  : dict IR     →  {"operation":"find", "table":"users", ...}
    """
    sql = sql.strip().rstrip(";")
    token = sql.split()[0].upper()

    parsers = {
        "SELECT":      _parse_select,
        "INSERT":      _parse_insert,
        "UPDATE":      _parse_update,
        "DELETE":      _parse_delete,
        "CREATE":      _parse_create,
        "DROP":        _parse_drop,
        "SHOW":        _parse_show,
    }

    if token not in parsers:
        raise SQLParseError(f"Operación SQL no reconocida: {token}")

    return parsers[token](sql)


# ── SELECT ────────────────────────────────────────────────────────────────────

def _parse_select(sql: str) -> dict:
    """
    Soporta:
      SELECT campo1, campo2 FROM tabla WHERE ...
      SELECT COUNT(*) FROM tabla WHERE ...
      SELECT SUM(campo) FROM tabla
      SELECT AVG(campo) FROM tabla
      SELECT DISTINCT campo FROM tabla
      SELECT ... FROM tabla INNER JOIN tabla2 ON tabla.id = tabla2.fk
    """
    sql_up = sql.upper()

    # ── agregaciones ──
    agg_map = {
        "COUNT": "count",
        "SUM":   "sum",
        "AVG":   "avg",
    }
    for keyword, operation in agg_map.items():
        # Busca COUNT(...), SUM(...), AVG(...)
        m = re.match(
            rf"SELECT\s+{keyword}\s*\(([^)]*)\)\s+FROM\s+(\w+)(.*)",
            sql, re.IGNORECASE
        )
        if m:
            field, table, rest = m.group(1).strip(), m.group(2), m.group(3)
            return {
                "operation": operation,
                "table":     table,
                "fields":    json.dumps([field]),
                "filter":    json.dumps(_extract_where(rest)),
                "options":   json.dumps({}),
            }

    # ── DISTINCT ──
    m = re.match(
        r"SELECT\s+DISTINCT\s+(\w+)\s+FROM\s+(\w+)(.*)",
        sql, re.IGNORECASE
    )
    if m:
        field, table, rest = m.group(1), m.group(2), m.group(3)
        return {
            "operation": "distinct",
            "table":     table,
            "fields":    json.dumps([field]),
            "filter":    json.dumps(_extract_where(rest)),
            "options":   json.dumps({}),
        }

    # ── INNER JOIN ──
    m = re.match(
        r"SELECT\s+(.*?)\s+FROM\s+(\w+)\s+INNER\s+JOIN\s+(\w+)\s+ON\s+(.+?)(?:\s+WHERE\s+(.+))?$",
        sql, re.IGNORECASE
    )
    if m:
        fields_raw, table, join_table, on_clause, where_raw = m.groups()
        return {
            "operation": "join",
            "table":     table,
            "fields":    json.dumps(_parse_fields(fields_raw)),
            "filter":    json.dumps(_parse_where_str(where_raw or "")),
            "options":   json.dumps({"join_table": join_table, "on": on_clause.strip()}),
        }

    # ── SELECT normal ──
    m = re.match(
        r"SELECT\s+(.*?)\s+FROM\s+(\w+)(.*)",
        sql, re.IGNORECASE
    )
    if not m:
        raise SQLParseError(f"No se pudo interpretar SELECT: {sql}")

    fields_raw, table, rest = m.group(1), m.group(2), m.group(3)
    return {
        "operation": "find",
        "table":     table,
        "fields":    json.dumps(_parse_fields(fields_raw)),
        "filter":    json.dumps(_extract_where(rest)),
        "options":   json.dumps(_extract_options(rest)),
    }


# ── INSERT ────────────────────────────────────────────────────────────────────

def _parse_insert(sql: str) -> dict:
    """
    INSERT INTO tabla (col1, col2) VALUES (val1, val2)
    """
    m = re.match(
        r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s+VALUES\s*\(([^)]+)\)",
        sql, re.IGNORECASE
    )
    if not m:
        raise SQLParseError(f"No se pudo interpretar INSERT: {sql}")

    table      = m.group(1)
    columns    = [c.strip() for c in m.group(2).split(",")]
    raw_values = [v.strip().strip("'\"") for v in m.group(3).split(",")]
    data       = dict(zip(columns, raw_values))

    return {
        "operation": "insert",
        "table":     table,
        "data":      json.dumps(data),
        "filter":    json.dumps({}),
        "options":   json.dumps({}),
    }


# ── UPDATE ────────────────────────────────────────────────────────────────────

def _parse_update(sql: str) -> dict:
    """
    UPDATE tabla SET col1 = val1, col2 = val2 WHERE ...
    """
    m = re.match(
        r"UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+)",
        sql, re.IGNORECASE
    )
    if not m:
        raise SQLParseError(f"No se pudo interpretar UPDATE: {sql}")

    table    = m.group(1)
    set_raw  = m.group(2)
    where_raw = m.group(3)

    data = {}
    for pair in set_raw.split(","):
        col, val = pair.split("=")
        data[col.strip()] = val.strip().strip("'\"")

    return {
        "operation": "update",
        "table":     table,
        "data":      json.dumps(data),
        "filter":    json.dumps(_parse_where_str(where_raw)),
        "options":   json.dumps({}),
    }


# ── DELETE ────────────────────────────────────────────────────────────────────

def _parse_delete(sql: str) -> dict:
    """
    DELETE FROM tabla WHERE ...
    """
    m = re.match(
        r"DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.+)",
        sql, re.IGNORECASE
    )
    if not m:
        raise SQLParseError(f"No se pudo interpretar DELETE: {sql}")

    return {
        "operation": "delete",
        "table":     m.group(1),
        "filter":    json.dumps(_parse_where_str(m.group(2))),
        "options":   json.dumps({}),
    }


# ── CREATE ────────────────────────────────────────────────────────────────────

def _parse_create(sql: str) -> dict:
    """
    CREATE DATABASE nombre
    CREATE TABLE nombre (col1 TIPO, col2 TIPO)
    CREATE COLLECTION nombre        ← extensión propia para modo colección
    """
    m_db = re.match(r"CREATE\s+DATABASE\s+(\w+)", sql, re.IGNORECASE)
    if m_db:
        return {"operation": "create_db", "database": m_db.group(1)}

    m_col = re.match(r"CREATE\s+COLLECTION\s+(\w+)", sql, re.IGNORECASE)
    if m_col:
        return {
            "operation": "create_table",
            "table":     m_col.group(1),
            "options":   json.dumps({"mode": "collection"}),
        }

    m_tbl = re.match(
        r"CREATE\s+TABLE\s+(\w+)\s*\((.+)\)",
        sql, re.IGNORECASE | re.DOTALL
    )
    if m_tbl:
        table  = m_tbl.group(1)
        schema = _parse_schema(m_tbl.group(2))
        return {
            "operation": "create_table",
            "table":     table,
            "options":   json.dumps({"mode": "table", "schema": schema}),
        }

    raise SQLParseError(f"No se pudo interpretar CREATE: {sql}")


# ── DROP ──────────────────────────────────────────────────────────────────────

def _parse_drop(sql: str) -> dict:
    """
    DROP DATABASE nombre
    DROP TABLE nombre
    """
    m_db = re.match(r"DROP\s+DATABASE\s+(\w+)", sql, re.IGNORECASE)
    if m_db:
        return {"operation": "drop_db", "database": m_db.group(1)}

    m_tbl = re.match(r"DROP\s+TABLE\s+(\w+)", sql, re.IGNORECASE)
    if m_tbl:
        return {"operation": "drop_table", "table": m_tbl.group(1)}

    raise SQLParseError(f"No se pudo interpretar DROP: {sql}")


# ── SHOW ──────────────────────────────────────────────────────────────────────

def _parse_show(sql: str) -> dict:
    """
    SHOW DATABASES
    SHOW TABLES
    """
    if re.match(r"SHOW\s+DATABASES", sql, re.IGNORECASE):
        return {"operation": "list_dbs"}

    if re.match(r"SHOW\s+TABLES", sql, re.IGNORECASE):
        return {"operation": "list_tables"}

    raise SQLParseError(f"No se pudo interpretar SHOW: {sql}")


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _parse_fields(raw: str) -> list:
    """'campo1, campo2' → ['campo1', 'campo2']  |  '*' → ['*']"""
    return [f.strip() for f in raw.split(",")]


def _extract_where(rest: str) -> dict:
    m = re.search(r"WHERE\s+(.+?)(?:\s+LIMIT|\s+ORDER|$)", rest, re.IGNORECASE)
    if not m:
        return {}
    return _parse_where_str(m.group(1))


def _parse_where_str(where: str) -> dict:
    """
    Convierte 'edad > 18 AND nombre = "Ana"' al formato de filtro IR.
    Soporta operadores: =  !=  >  >=  <  <=
    Condiciones múltiples unidas por AND (OR no requerido por el proyecto).
    """
    if not where.strip():
        return {}

    op_map = {
        ">=": "$gte",
        "<=": "$lte",
        "!=": "$ne",
        ">":  "$gt",
        "<":  "$lt",
        "=":  "$eq",
    }
    result = {}
    parts = re.split(r"\s+AND\s+", where, flags=re.IGNORECASE)
    for part in parts:
        for sym, mongo_op in op_map.items():
            m = re.match(rf"(\w+)\s*{re.escape(sym)}\s*['\"]?([^'\"]+)['\"]?", part.strip())
            if m:
                col, val = m.group(1), m.group(2).strip()
                # intenta convertir a número
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                result[col] = {mongo_op: val}
                break
    return result


def _extract_options(rest: str) -> dict:
    opts = {}
    m_limit = re.search(r"LIMIT\s+(\d+)", rest, re.IGNORECASE)
    if m_limit:
        opts["limit"] = int(m_limit.group(1))
    return opts


def _parse_schema(raw: str) -> list:
    """
    'id INT, nombre VARCHAR(100), activo BOOLEAN'
    → [{"column":"id","type":"INT"}, ...]
    """
    cols = []
    for col_def in raw.split(","):
        parts = col_def.strip().split()
        if len(parts) >= 2:
            cols.append({"column": parts[0], "type": parts[1]})
    return cols
