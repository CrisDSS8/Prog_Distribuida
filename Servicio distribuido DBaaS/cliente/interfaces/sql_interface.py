"""
sql_interface.py
Terminal SQL interactiva. El usuario escribe queries MySQL
y el resultado se muestra formateado en pantalla.
"""

import os
from gateway_client import GatewayClient


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


class SQLInterface:

    def __init__(self, session: dict):
        self.session  = session
        self.client   = GatewayClient()
        self.active_db = None           # base de datos seleccionada

    def run(self):
        _clear()                        
        self._banner()
        while True:
            try:
                prompt = f"  sql [{self.active_db or '---'}]> "
                query  = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Sesión terminada.")
                _clear()
                break

            if not query:
                continue

            # comandos locales del cliente
            if query.lower() in ("exit", "quit", "\\q"):
                _clear()                
                break

            if query.lower().startswith("use "):
                self.active_db = query.split()[1].rstrip(";")
                print(f"  Base de datos activa: {self.active_db}")
                continue

            if query.lower() in ("help", "\\h"):
                self._help()
                continue

            # enviar al servidor
            result = self.client.send_sql(query, self.active_db, self.session)
            self._print_result(result)

    # -- Presentación 

    def _print_result(self, result: dict):
        if not result["success"]:
            print(f"\n  ✗ Error: {result['message']}\n")
            return

        # Operaciones que devuelven documentos (SELECT / JOIN)
        if "documents" in result and result["documents"]:
            docs = result["documents"]
            keys = list(docs[0].keys())
            col_w = {k: max(len(k), max(len(str(d.get(k,""))) for d in docs)) for k in keys}

            header = "  " + " | ".join(k.ljust(col_w[k]) for k in keys)
            sep    = "  " + "-|-".join("─" * col_w[k] for k in keys)
            print()
            print(header)
            print(sep)
            for doc in docs:
                row = "  " + " | ".join(str(doc.get(k,"")).ljust(col_w[k]) for k in keys)
                print(row)
            print(f"\n  {len(docs)} resultado(s)\n")
            return

        # Agregaciones escalares (COUNT, SUM, AVG)
        if "value" in result:
            print(f"\n  Resultado: {result['value']}\n")
            return

        # DISTINCT
        if "values" in result:
            print(f"\n  Valores únicos: {', '.join(str(v) for v in result['values'])}\n")
            return

        # Listas (SHOW DATABASES / SHOW TABLES)
        if "databases" in result:
            print()
            for db in result["databases"]:
                print(f"  • {db}")
            print()
            return

        if "tables" in result:
            print()
            for t in result["tables"]:
                print(f"  • {t}")
            print()
            return

        # Operaciones de escritura
        rows = result.get("affected_rows", 0)
        msg  = result.get("message", "OK")
        print(f"\n  ✓ {msg}" + (f"  ({rows} fila(s) afectada(s))" if rows else "") + "\n")

    def _banner(self):
        print(f"""
  
     Modo SQL — sintaxis MySQL          
     Usuario: {self.session['username']:<26}
     Rol:     {self.session['role']:<26}
  
  Escribe 'USE nombre_db' para seleccionar base de datos.
  Escribe 'exit' o 'quit' para salir.
""")

    def _help(self):
        print("""
  Ejemplos de queries soportadas:
  -----------------------------------------------------
  SHOW DATABASES;
  SHOW TABLES;
  CREATE DATABASE mi_db;
  DROP DATABASE mi_db;
  USE mi_db;

  CREATE TABLE empleados (id INT, nombre VARCHAR(100), salario FLOAT);
  CREATE COLLECTION documentos;
  DROP TABLE empleados;

  INSERT INTO empleados (id, nombre, salario) VALUES (1, 'Ana', 4500);
  SELECT nombre, salario FROM empleados WHERE salario > 3000;
  SELECT COUNT(*) FROM empleados;
  SELECT SUM(salario) FROM empleados WHERE activo = 1;
  SELECT AVG(salario) FROM empleados;
  SELECT DISTINCT nombre FROM empleados;
  SELECT * FROM pedidos INNER JOIN clientes ON pedidos.cliente_id = clientes.id;
  UPDATE empleados SET salario = 5000 WHERE id = 1;
  DELETE FROM empleados WHERE id = 1;
  -----------------------------------------------------
""")