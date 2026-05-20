"""
aggregations.py
Ejecuta COUNT, SUM, AVG, DISTINCT contra MySQL
y para SUM/AVG/COUNT lanza mpi_worker.py en paralelo.

JOIN se maneja en join_executor.py por separado.
"""

import json
import os
import subprocess
import mysql.connector


MPI_WORKERS  = int(os.getenv("MPI_WORKERS", "4"))   # número de procesos MPI
WORKER_PATH  = os.path.join(os.path.dirname(__file__), "mpi_worker.py")


def _conn(database: str):
    return mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", "dbaas1234"),
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


# ── Helpers de query ──────────────────────────────────────────────────────────

def _build_where(filt: dict, col_mode: bool) -> tuple[str, list]:
    """Mismo builder que ir_to_sql pero local para este servicio."""
    if not filt:
        return "", []

    OP_MAP = {"$eq": "=", "$ne": "!=", "$gt": ">",
              "$gte": ">=", "$lt": "<", "$lte": "<="}
    conditions, params = [], []

    for field, condition in filt.items():
        if isinstance(condition, dict):
            for op, val in condition.items():
                sql_op = OP_MAP.get(op, "=")
                col    = f"JSON_EXTRACT(_data,'$.{field}')" if col_mode else f"`{field}`"
                conditions.append(f"{col} {sql_op} %s")
                params.append(val)
        else:
            col = f"JSON_EXTRACT(_data,'$.{field}')" if col_mode else f"`{field}`"
            conditions.append(f"{col} = %s")
            params.append(condition)

    return " WHERE " + " AND ".join(conditions), params


def _fetch_values(database: str, table: str, field: str,
                  filt: dict, col_mode: bool) -> list:
    """
    Obtiene la lista de valores de un campo desde MySQL.
    Estos valores son los que se distribuyen entre los workers MPI.
    """
    if col_mode:
        col_expr = f"JSON_EXTRACT(_data, '$.{field}')"
    else:
        col_expr = f"`{field}`"

    where, params = _build_where(filt, col_mode)
    query = f"SELECT {col_expr} FROM `{table}`{where}"

    con = _conn(database)
    cur = con.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); con.close()

    # extraer solo el valor numérico de cada fila
    values = []
    for row in rows:
        val = row[0]
        if val is not None:
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                pass
    return values


# ── MPI launcher ──────────────────────────────────────────────────────────────

def _run_mpi(op: str, values: list) -> float:
    """
    Lanza mpi_worker.py con mpiexec y le pasa los datos por stdin como JSON.
    Retorna el resultado numérico final.
    """
    payload = json.dumps({"op": op, "data": values})

    result = subprocess.run(
        ["mpiexec", "-n", str(MPI_WORKERS), "python", WORKER_PATH],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"MPI falló: {result.stderr.strip()}")

    # el rank 0 imprime el resultado como JSON en stdout
    # filtramos solo la última línea que contiene el JSON
    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)["value"]

    raise RuntimeError("MPI no produjo resultado legible")


# ── Operaciones públicas ──────────────────────────────────────────────────────

def count(ir: dict) -> dict:
    try:
        database = ir["database"]
        table    = ir["table"]
        filt     = json.loads(ir.get("filter", "{}"))
        col_mode = _is_collection(database, table)

        # COUNT no necesita un campo numérico específico, cuenta filas
        where, params = _build_where(filt, col_mode)
        query = f"SELECT COUNT(*) FROM `{table}`{where}"

        con = _conn(database)
        cur = con.cursor()
        cur.execute(query, params)
        total = cur.fetchone()[0]
        cur.close(); con.close()

        # lanzar MPI igual para mantener consistencia con el requisito,
        # aunque COUNT sea trivial: distribuimos la lista de 1s y sumamos
        values = [1.0] * int(total)
        value  = _run_mpi("count", values)

        return {"success": True, "value": value}
    except Exception as e:
        return {"success": False, "value": 0.0, "message": str(e)}


def sum_field(ir: dict) -> dict:
    try:
        database = ir["database"]
        table    = ir["table"]
        field    = json.loads(ir.get("fields", '["*"]'))[0]
        filt     = json.loads(ir.get("filter", "{}"))
        col_mode = _is_collection(database, table)

        values = _fetch_values(database, table, field, filt, col_mode)
        value  = _run_mpi("sum", values)

        return {"success": True, "value": value}
    except Exception as e:
        return {"success": False, "value": 0.0, "message": str(e)}


def avg_field(ir: dict) -> dict:
    try:
        database = ir["database"]
        table    = ir["table"]
        field    = json.loads(ir.get("fields", '["*"]'))[0]
        filt     = json.loads(ir.get("filter", "{}"))
        col_mode = _is_collection(database, table)

        values = _fetch_values(database, table, field, filt, col_mode)
        value  = _run_mpi("avg", values)

        return {"success": True, "value": value}
    except Exception as e:
        return {"success": False, "value": 0.0, "message": str(e)}


def distinct(ir: dict) -> dict:
    try:
        database = ir["database"]
        table    = ir["table"]
        field    = json.loads(ir.get("fields", '["*"]'))[0]
        filt     = json.loads(ir.get("filter", "{}"))
        col_mode = _is_collection(database, table)

        if col_mode:
            col_expr = f"DISTINCT JSON_EXTRACT(_data, '$.{field}')"
        else:
            col_expr = f"DISTINCT `{field}`"

        where, params = _build_where(filt, col_mode)
        query = f"SELECT {col_expr} FROM `{table}`{where}"

        con = _conn(database)
        cur = con.cursor()
        cur.execute(query, params)
        values = [str(row[0]) for row in cur.fetchall() if row[0] is not None]
        cur.close(); con.close()

        return {"success": True, "values": values}
    except Exception as e:
        return {"success": False, "values": [], "message": str(e)}
