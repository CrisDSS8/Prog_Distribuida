"""
user_store.py
Acceso a la tabla de usuarios en MySQL.
Las contraseñas se guardan hasheadas con bcrypt, nunca en texto plano.
"""

import bcrypt
import mysql.connector
import os
import uuid

# ── Conexión ──────────────────────────────────────────────────────────────────

def _conn():
    return mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
        database = os.getenv("DB_NAME",     "dbaas_auth"),
    )


# ── Inicialización ────────────────────────────────────────────────────────────

def init():
    """
    Crea la base de datos y la tabla de usuarios si no existen.
    Se llama una vez al arrancar el servicio.
    """
    # primero conectar sin seleccionar DB para crearla
    con = mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
    )
    cur = con.cursor()
    db  = os.getenv("DB_NAME", "dbaas_auth")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
    cur.execute(f"USE `{db}`")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    VARCHAR(36)  PRIMARY KEY,
            username   VARCHAR(100) UNIQUE NOT NULL,
            password   VARCHAR(255) NOT NULL,
            role       ENUM('admin','write','read') NOT NULL DEFAULT 'read',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    cur.close()
    con.close()
    print("[auth] tabla users lista")


# ── Operaciones ───────────────────────────────────────────────────────────────

def create_user(username: str, password: str, role: str) -> dict:
    """
    Registra un nuevo usuario.
    Retorna {"success": bool, "message": str}
    """
    # validar rol
    if role not in ("admin", "write", "read"):
        return {"success": False, "message": f"Rol inválido: {role}"}

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    uid    = str(uuid.uuid4())

    try:
        con = _conn()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO users (user_id, username, password, role) VALUES (%s, %s, %s, %s)",
            (uid, username, hashed, role),
        )
        con.commit()
        return {"success": True, "message": "Usuario registrado"}
    except mysql.connector.IntegrityError:
        return {"success": False, "message": f"El usuario '{username}' ya existe"}
    except Exception as e:
        return {"success": False, "message": f"Error al registrar: {str(e)}"}
    finally:
        cur.close()
        con.close()


def verify_user(username: str, password: str) -> dict:
    """
    Verifica credenciales.
    Retorna {"success": bool, "user_id": str, "role": str, "message": str}
    """
    try:
        con = _conn()
        cur = con.cursor(dictionary=True)
        cur.execute(
            "SELECT user_id, password, role FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()

        if not row:
            return {"success": False, "message": "Usuario no encontrado"}

        if not bcrypt.checkpw(password.encode(), row["password"].encode()):
            return {"success": False, "message": "Contraseña incorrecta"}

        return {
            "success": True,
            "user_id": row["user_id"],
            "role":    row["role"],
            "message": "OK",
        }
    except Exception as e:
        return {"success": False, "message": f"Error al verificar: {str(e)}"}
    finally:
        cur.close()
        con.close()
