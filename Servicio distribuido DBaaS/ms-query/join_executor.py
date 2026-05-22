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
    """
    Convierte el filtro IR a WHERE para JOINs.
    En JOINs el usuario debe pasar el campo con prefijo de tabla
    para evitar ambigüedad: {"pedidos.cliente_id": {"$eq": 1}}
    Si no tiene prefijo se usa tal cual y MySQL lanzará error si es ambiguo.
    """
    if not filt:
        return "", []
    OP_MAP = {"$eq": "=", "$ne": "!=", "$gt": ">",
              "$gte": ">=", "$lt": "<", "$lte": "<="}
    conditions, params = [], []
    for field, condition in filt.items():
        # el campo puede venir como "tabla.campo" o solo "campo"
        col = field  # se usa directamente sin backticks para permitir tabla.campo
        if isinstance(condition, dict):
            for op, val in condition.items():
                conditions.append(f"{col} {OP_MAP.get(op,'=')} %s")
                params.append(val)
        else:
            conditions.append(f"{col} = %s")
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
        # prefijar cada columna con alias tabla para evitar colisiones de nombre
        select = (
            f"SELECT "
            f"`{table_a}`.id      AS `{table_a}.id`, "
            f"`{table_a}`.nombre  AS `{table_a}.nombre`, "
            f"`{table_a}`.*,      "
            f"`{table_b}`.id      AS `{table_b}.id`, "
            f"`{table_b}`.nombre  AS `{table_b}.nombre`, "
            f"`{table_b}`.*"
        )
        # forma más limpia: traer todo y prefijar en Python
        select = f"SELECT `{table_a}`.*, `{table_b}`.*"
    else:
        select = "SELECT " + ", ".join(fields)

    where, params = _build_where(filt)
    query = (f"{select} FROM `{table_a}` "
             f"INNER JOIN `{table_b}` ON {on_clause}{where}")

    con = _conn(database)
    # usar cursor normal (no dictionary) para obtener descripción de columnas
    cur = con.cursor()
    cur.execute(query, params)
    col_names = [desc[0] for desc in cur.description]
    col_tables = [desc[1] for desc in cur.description] if hasattr(cur, 'description') else []
    raw_rows   = cur.fetchall()
    cur.close(); con.close()

    # reconstruir filas prefijando columnas duplicadas con nombre de tabla
    rows = _prefix_duplicate_cols(col_names, raw_rows, table_a, table_b, query, database)

    return {"success": True, "documents": rows, "message": "OK"}


def _prefix_duplicate_cols(col_names, raw_rows, table_a, table_b, query, database) -> list:
    """
    Prefija columnas duplicadas con el nombre de la tabla.
    id → pedidos.id y clientes.id en lugar de que uno pise al otro.
    """
    # contar cuántas veces aparece cada nombre de columna
    from collections import Counter
    counts = Counter(col_names)

    # construir nombres únicos
    seen    = {}
    headers = []
    for col in col_names:
        if counts[col] > 1:
            # asignar prefijo según orden de aparición
            seen[col] = seen.get(col, 0) + 1
            table_prefix = table_a if seen[col] == 1 else table_b
            headers.append(f"{table_prefix}.{col}")
        else:
            headers.append(col)

    return [dict(zip(headers, row)) for row in raw_rows]


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

    # hacer el join prefijando campos para evitar colisiones
    joined = []
    for row_a in rows_a:
        k = str(row_a.get(key_a))
        for row_b in index_b.get(k, []):
            # detectar claves duplicadas entre las dos filas
            keys_a    = set(row_a.keys())
            keys_b    = set(row_b.keys())
            duplicates = keys_a & keys_b

            merged = {}
            for key, val in row_a.items():
                if key in duplicates:
                    merged[f"{table_a}.{key}"] = val  # pedidos.id, pedidos.nombre
                else:
                    merged[key] = val
            for key, val in row_b.items():
                if key in duplicates:
                    merged[f"{table_b}.{key}"] = val  # clientes.id, clientes.nombre
                else:
                    merged[key] = val

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
