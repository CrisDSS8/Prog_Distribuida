"""
jwt_handler.py
Genera y valida tokens JWT.
La clave secreta viene de variable de entorno JWT_SECRET.
Expiración por defecto: 24 horas.
"""

import jwt
import os
from datetime import datetime, timezone, timedelta

SECRET    = os.getenv("JWT_SECRET", "cambia_esto_en_produccion")
ALGORITHM = "HS256"
EXP_HOURS = int(os.getenv("JWT_EXP_HOURS", "24"))


def generate(user_id: str, username: str, role: str) -> str:
    """
    Genera un JWT firmado con los datos del usuario.
    Payload:
        user_id  : id único del usuario
        username : nombre de usuario
        role     : "admin" | "write" | "read"
        iat      : emitido en (timestamp)
        exp      : expira en (iat + EXP_HOURS)
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id":  user_id,
        "username": username,
        "role":     role,
        "iat":      now,
        "exp":      now + timedelta(hours=EXP_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def validate(token: str) -> dict:
    """
    Valida el JWT y retorna su payload si es correcto.

    Retorna:
        {"valid": True,  "user_id": ..., "username": ..., "role": ...}
        {"valid": False, "message": "razón del fallo"}
    """
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return {
            "valid":    True,
            "user_id":  payload["user_id"],
            "username": payload["username"],
            "role":     payload["role"],
        }
    except jwt.ExpiredSignatureError:
        return {"valid": False, "message": "Token expirado"}
    except jwt.InvalidTokenError as e:
        return {"valid": False, "message": f"Token inválido: {str(e)}"}
