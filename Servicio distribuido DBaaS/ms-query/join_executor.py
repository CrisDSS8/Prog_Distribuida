"""
join_executor.py
Ejecuta INNER JOIN entre dos tablas.
Soporta tablas normales, colecciones JSON, o mezcla de ambas.
El campo 'options' de la IR lleva:
  {"join_table": "tabla_b", "on": "tabla_a.id = tabla_b.user_id"}
"""

import json
import mysql.connector
import os


def _conn(database: str):
    return mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
        database = database,
    )


def _is_collection(database: str, table: str) -> bool:
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE '_data'")
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        cur.close(); con.close()


def _build_where(filt: dict) -> tuple[str, list]:
    if not filt:
        return "", []
    OP_MAP = {"$eq": "=", "$ne": "!=", "$gt": ">",
              "$gte": ">=", "$lt": "<", "$lte": "<="}
    conditions, params = [], []
    for field, condition in filt.items():
        if isinstance(condition, dict):
            for op, val in condition.items():
                conditions.append(f"{field} {OP_MAP.get(op,'=')} %s")
                params.append(val)
        else:
            conditions.append(f"{field} = %s")
            params.append(condition)
    return " WHERE " + " AND ".join(conditions), params


def execute_join(ir: dict) -> dict:
    """
    Construye y ejecuta un INNER JOIN entre tabla_a y tabla_b.
    Si alguna es colección, hace el join en Python después de obtener las filas.
    """
    try:
        database   = ir["database"]
        table_a    = ir["table"]
        fields     = json.loads(ir.get("fields", '["*"]'))
        filt       = json.loads(ir.get("filter", "{}"))
        options    = json.loads(ir.get("options", "{}"))

        table_b    = options.get("join_table")
        on_clause  = options.get("on")

        if not table_b or not on_clause:
            return {"success": False, "documents": [],
                    "message": "join requiere 'join_table' y 'on' en options"}

        col_a = _is_collection(database, table_a)
        col_b = _is_collection(database, table_b)

        # ── Ambas son tablas normales: JOIN directo en MySQL ──────────────────
        if not col_a and not col_b:
            return _join_sql(database, table_a, table_b, on_clause, fields, filt)

        # ── Al menos una es colección: JOIN en Python ─────────────────────────
        return _join_python(database, table_a, table_b, on_clause, fields, filt, col_a, col_b)

    except Exception as e:
        return {"success": False, "documents": [], "message": str(e)}


def _join_sql(database, table_a, table_b, on_clause, fields, filt) -> dict:
    """JOIN directo en MySQL para dos tablas normales."""
    if fields == ["*"]:
        select = f"SELECT `{table_a}`.*, `{table_b}`.*"
    else:
        select = "SELECT " + ", ".join(fields)

    where, params = _build_where(filt)
    query = (f"{select} FROM `{table_a}` "
             f"INNER JOIN `{table_b}` ON {on_clause}{where}")

    con = _conn(database)
    cur = con.cursor(dictionary=True)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()

    return {"success": True, "documents": rows, "message": "OK"}


def _join_python(database, table_a, table_b, on_clause,
                 fields, filt, col_a, col_b) -> dict:
    """
    JOIN en Python cuando alguna tabla es colección.
    Parsea 'on_clause' para extraer los campos de unión.
    Ejemplo: "pedidos.cliente_id = clientes.id"
    """
    # parsear on_clause → (tabla_a.campo_a, tabla_b.campo_b)
    try:
        left, right = [s.strip() for s in on_clause.split("=")]
        # left  → "pedidos.cliente_id"  → campo "cliente_id" en tabla_a
        # right → "clientes.id"         → campo "id" en tabla_b
        key_a = left.split(".")[-1]
        key_b = right.split(".")[-1]
    except ValueError:
        return {"success": False, "documents": [],
                "message": f"No se pudo parsear ON: {on_clause}"}

    rows_a = _fetch_all(database, table_a, col_a)
    rows_b = _fetch_all(database, table_b, col_b)

    # indexar tabla_b por su clave de join para O(n) en vez de O(n²)
    index_b = {}
    for row in rows_b:
        k = str(row.get(key_b))
        index_b.setdefault(k, []).append(row)

    # hacer el join
    joined = []
    for row_a in rows_a:
        k = str(row_a.get(key_a))
        for row_b in index_b.get(k, []):
            merged = {**row_a, **row_b}
            if fields != ["*"]:
                merged = {f: merged[f] for f in fields if f in merged}
            joined.append(merged)

    return {"success": True, "documents": joined, "message": "OK"}


def _fetch_all(database: str, table: str, col_mode: bool) -> list:
    """Obtiene todas las filas de una tabla como lista de dicts."""
    con = _conn(database)
    cur = con.cursor(dictionary=True)
    cur.execute(f"SELECT * FROM `{table}`")
    rows = cur.fetchall()
    cur.close(); con.close()

    if col_mode:
        result = []
        for row in rows:
            doc = json.loads(row["_data"]) if isinstance(row["_data"], str) else row["_data"]
            doc["_id"] = row["_id"]
            result.append(doc)
        return result

    return [dict(r) for r in rows]
