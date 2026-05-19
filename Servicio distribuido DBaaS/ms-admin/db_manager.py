"""
db_manager.py
Toda la lógica de administración contra MySQL.
Crea/elimina bases de datos lógicas y tablas o colecciones.
Las colecciones son tablas MySQL con una columna JSON (_data).
"""

import json
import mysql.connector
import os


def _conn(database: str = None):
    params = dict(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
    )
    if database:
        params["database"] = database
    return mysql.connector.connect(**params)


# ── Bases de datos ────────────────────────────────────────────────────────────

def create_database(name: str) -> dict:
    try:
        con = _conn()
        cur = con.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}`")
        con.commit()
        return {"success": True, "message": f"Base de datos '{name}' creada"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cur.close(); con.close()


def drop_database(name: str) -> dict:
    # proteger la base de datos interna del sistema
    if name in ("dbaas_auth", "information_schema", "mysql", "performance_schema"):
        return {"success": False, "message": f"No se puede eliminar '{name}'"}
    try:
        con = _conn()
        cur = con.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        con.commit()
        return {"success": True, "message": f"Base de datos '{name}' eliminada"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cur.close(); con.close()


def list_databases() -> dict:
    try:
        con = _conn()
        cur = con.cursor()
        cur.execute("SHOW DATABASES")
        # excluir bases de datos internas de MySQL y del sistema
        excluded = {"information_schema", "mysql", "performance_schema", "sys", "dbaas_auth"}
        dbs = [row[0] for row in cur.fetchall() if row[0] not in excluded]
        return {"success": True, "databases": dbs}
    except Exception as e:
        return {"success": False, "databases": [], "message": str(e)}
    finally:
        cur.close(); con.close()


# ── Tablas y colecciones ──────────────────────────────────────────────────────

def create_table(database: str, table: str, mode: str, schema: list) -> dict:
    """
    mode='table'      → crea tabla con columnas definidas en schema
    mode='collection' → crea tabla con estructura fija para documentos JSON
    """
    try:
        con = _conn(database)
        cur = con.cursor()

        if mode == "collection":
            sql = f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    _id        VARCHAR(36)  PRIMARY KEY,
                    _data      JSON         NOT NULL,
                    _created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:
            # construir columnas desde el schema
            if not schema:
                return {"success": False, "message": "Se requiere schema para modo tabla"}
            cols = _build_columns(schema)
            sql  = f"CREATE TABLE IF NOT EXISTS `{table}` ({cols})"

        cur.execute(sql)
        con.commit()
        return {"success": True, "message": f"'{table}' creada en '{database}'"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cur.close(); con.close()


def drop_table(database: str, table: str) -> dict:
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute(f"DROP TABLE IF EXISTS `{table}`")
        con.commit()
        return {"success": True, "message": f"'{table}' eliminada de '{database}'"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cur.close(); con.close()


def list_tables(database: str) -> dict:
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
        return {"success": True, "tables": tables}
    except Exception as e:
        return {"success": False, "tables": [], "message": str(e)}
    finally:
        cur.close(); con.close()


# ── Helper ────────────────────────────────────────────────────────────────────

# Tipos SQL que el sistema acepta desde el cliente
TYPE_MAP = {
    "INT":       "INT",
    "INTEGER":   "INT",
    "FLOAT":     "FLOAT",
    "DOUBLE":    "DOUBLE",
    "VARCHAR":   "VARCHAR(255)",
    "TEXT":      "TEXT",
    "BOOLEAN":   "BOOLEAN",
    "BOOL":      "BOOLEAN",
    "DATE":      "DATE",
    "TIMESTAMP": "TIMESTAMP",
}

def _build_columns(schema: list) -> str:
    """
    schema: [{"column": "id", "type": "INT"}, ...]
    Produce: `id` INT, `nombre` VARCHAR(255), ...
    La primera columna INT se convierte en PRIMARY KEY AUTO_INCREMENT.
    """
    parts = []
    pk_set = False
    for col in schema:
        name    = col.get("column", "")
        raw     = col.get("type", "VARCHAR").upper().split("(")[0]
        sql_type = TYPE_MAP.get(raw, "VARCHAR(255)")

        if not pk_set and sql_type == "INT":
            parts.append(f"`{name}` INT AUTO_INCREMENT PRIMARY KEY")
            pk_set = True
        else:
            parts.append(f"`{name}` {sql_type}")

    return ", ".join(parts)
