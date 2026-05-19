"""
role_guard.py
Define qué operaciones están permitidas por rol.
El Gateway consulta esto antes de reenviar cualquier petición al broker.
"""

# Operaciones agrupadas por categoría
ADMIN_OPS  = {"create_db", "drop_db", "list_dbs",
              "create_table", "drop_table", "list_tables"}
WRITE_OPS  = {"insert", "update", "delete"}
READ_OPS   = {"find", "count", "sum", "avg", "distinct", "join"}

# Permisos acumulativos: admin puede todo, write puede write+read, read solo read
PERMISSIONS = {
    "admin": ADMIN_OPS | WRITE_OPS | READ_OPS,
    "write": WRITE_OPS | READ_OPS,
    "read":  READ_OPS,
}


def is_allowed(role: str, operation: str) -> bool:
    """
    Retorna True si el rol puede ejecutar la operación.
    Si el rol no existe, deniega por defecto.
    """
    return operation in PERMISSIONS.get(role, set())


def denial_message(role: str, operation: str) -> str:
    return f"El rol '{role}' no tiene permiso para ejecutar '{operation}'"
