"""
executor.py
Ejecuta queries MySQL y devuelve resultados normalizados.
También detecta si una tabla es colección (tiene columna _data JSON)
para que ir_to_sql sepa qué modo usar.
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


def is_collection(database: str, table: str) -> bool:
    """
    Una tabla es colección si tiene la columna '_data'.
    Esto permite al CRUD Service saber qué modo de query usar.
    """
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE '_data'")
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        cur.close(); con.close()


def run_insert(database: str, query: str, params: list) -> dict:
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute(query, params)
        con.commit()
        return {
            "success":       True,
            "message":       "Registro insertado",
            "affected_rows": cur.rowcount,
        }
    except Exception as e:
        return {"success": False, "message": str(e), "affected_rows": 0}
    finally:
        cur.close(); con.close()


def run_find(database: str, query: str, params: list,
             collection_mode: bool, fields: list) -> dict:
    try:
        con = _conn(database)
        cur = con.cursor(dictionary=True)
        cur.execute(query, params)
        rows = cur.fetchall()

        if collection_mode:
            # extraer el documento JSON de _data y añadir _id
            docs = []
            for row in rows:
                doc = json.loads(row["_data"]) if isinstance(row["_data"], str) else row["_data"]
                doc["_id"] = row["_id"]
                # filtrar campos si el usuario especificó cuáles quiere
                if fields and fields != ["*"]:
                    doc = {k: v for k, v in doc.items() if k in fields}
                docs.append(doc)
        else:
            docs = [dict(row) for row in rows]

        return {"success": True, "message": "OK", "documents": docs}
    except Exception as e:
        return {"success": False, "message": str(e), "documents": []}
    finally:
        cur.close(); con.close()


def run_write(database: str, query: str, params: list, op: str) -> dict:
    """Para UPDATE y DELETE."""
    try:
        con = _conn(database)
        cur = con.cursor()
        cur.execute(query, params)
        con.commit()
        messages = {"update": "Registro(s) actualizado(s)", "delete": "Registro(s) eliminado(s)"}
        return {
            "success":       True,
            "message":       messages.get(op, "OK"),
            "affected_rows": cur.rowcount,
        }
    except Exception as e:
        return {"success": False, "message": str(e), "affected_rows": 0}
    finally:
        cur.close(); con.close()
