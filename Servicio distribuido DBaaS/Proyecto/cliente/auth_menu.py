"""
auth_menu.py
Maneja login y registro antes de cualquier otra interacción.
Habla directamente con el Auth Service vía el Gateway.
"""

import getpass
from gateway_client import GatewayClient

client = GatewayClient()


def auth_flow() -> dict | None:
    """
    Retorna un dict de sesión:
      {"token": str, "role": str, "username": str}
    o None si el usuario elige salir.
    """
    while True:
        print("""
  -- Autenticación ----------------------
    1. Iniciar sesión
    2. Registrarse
    0. Salir
  ---------------------------------------""")

        opt = input("  Opción: ").strip()

        if opt == "1":
            session = _login()
            if session:
                return session

        elif opt == "2":
            _register()

        elif opt == "0":
            return None

        else:
            print("  Opción no válida.")


def _login() -> dict | None:
    print("\n  -- Login --")
    username = input("  Usuario: ").strip()
    password = getpass.getpass("  Contraseña: ")

    result = client.login(username, password)

    if result["success"]:
        return {
            "token":    result["token"],
            "role":     result["role"],
            "username": username,
        }

    print(f"\n  ✗ {result['message']}")
    return None


def _register():
    print("\n  -- Registro --")
    username = input("  Nuevo usuario: ").strip()
    password = getpass.getpass("  Contraseña: ")
    confirm  = getpass.getpass("  Confirmar contraseña: ")

    if password != confirm:
        print("\n  ✗ Las contraseñas no coinciden.")
        return

    print("""
  Rol:
    1. Lectura   — solo puede consultar datos
    2. Escritura — puede leer y modificar datos
    3. Admin     — acceso completo
""")
    roles = {"1": "read", "2": "write", "3": "admin"}
    role  = roles.get(input("  Rol: ").strip(), "read")

    result = client.register(username, password, role)

    if result["success"]:
        print("\n  ✓ Usuario registrado. Ahora puedes iniciar sesión.")
    else:
        print(f"\n  ✗ {result['message']}")
