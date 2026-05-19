"""
main.py
Punto de entrada del cliente DBaaS.
Orden: login/registro → selección de interfaz → menú correspondiente.
"""

from auth_menu import auth_flow
from interfaces.sql_interface import SQLInterface
from interfaces.nosql_interface import NoSQLInterface


def main():
    _banner()

    # ── 1. Login / Registro ───────────────────────────────────────────────────
    session = auth_flow()          # retorna {"token": "...", "role": "...", "username": "..."}
    if not session:
        print("No se pudo autenticar. Saliendo.")
        return

    print(f"\n  Bienvenido, {session['username']} [{session['role']}]")

    # ── 2. Selección de interfaz ──────────────────────────────────────────────
    interface = _pick_interface()
    if not interface:
        return

    # ── 3. Menú correspondiente ───────────────────────────────────────────────
    if interface == "sql":
        SQLInterface(session).run()
    else:
        NoSQLInterface(session).run()


def _banner():
    print("""
╔══════════════════════════════════════╗
║         DBaaS — Cliente              ║
║  Servicio distribuido de bases datos  ║
╚══════════════════════════════════════╝""")


def _pick_interface() -> str | None:
    print("""
  ¿Con qué interfaz deseas trabajar?

    1. SQL   — escribe queries MySQL directamente
    2. NoSQL — menú guiado, sin necesidad de conocer sintaxis
    0. Salir
""")
    while True:
        opt = input("  Opción: ").strip()
        if opt == "1":
            return "sql"
        if opt == "2":
            return "nosql"
        if opt == "0":
            return None
        print("  Opción no válida, intenta de nuevo.")


if __name__ == "__main__":
    main()
