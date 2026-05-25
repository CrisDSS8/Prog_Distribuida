"""
role_guard.py
Define qué operaciones están permitidas por rol.
El Gateway consulta esto antes de reenviar cualquier petición al broker.
"""

# Operaciones agrupadas por categoría
ADMIN_OPS  = {"create_db", "drop_db", "create_table", "drop_table"}
LIST_OPS   = {"list_dbs", "list_tables"}           # cualquier rol puede listar
WRITE_OPS  = {"insert", "update", "delete"}
READ_OPS   = {"find", "count", "sum", "avg", "distinct", "join"}

# Permisos acumulativos
PERMISSIONS = {
    "admin": ADMIN_OPS | LIST_OPS | WRITE_OPS | READ_OPS,
    "write": LIST_OPS | WRITE_OPS | READ_OPS,
    "read":  LIST_OPS | READ_OPS,
}


def is_allowed(role: str, operation: str) -> bool:
    """
    Retorna True si el rol puede ejecutar la operación.
    Si el rol no existe, deniega por defecto.
    """
    return operation in PERMISSIONS.get(role, set())


def denial_message(role: str, operation: str) -> str:
    return f"El rol '{role}' no tiene permiso para ejecutar '{operation}'"