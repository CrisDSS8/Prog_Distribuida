"""
nosql_interface.py
Menú guiado NoSQL. El usuario elige opciones numeradas y responde
preguntas simples. El cliente construye el JSON internamente.
El usuario nunca ve ni escribe JSON.
"""

import os
from gateway_client import GatewayClient


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


class NoSQLInterface:

    def __init__(self, session: dict):
        self.session   = session
        self.client    = GatewayClient()
        self.active_db = None
        self.role      = session["role"]

    def run(self):
        _clear()
        self._banner()
        while True:
            self._main_menu()
            opt = input("  Opción: ").strip()

            if opt == "0":
                _clear()
                break
            elif opt == "1":
                self._menu_databases()
            elif opt == "2":
                self._menu_collections()
            elif opt == "3":
                self._menu_crud()
            elif opt == "4":
                self._menu_queries()
            else:
                print("  Opción no válida.\n")

    # -- Menús

    def _main_menu(self):
        db_label = self.active_db or "ninguna"
        print(f"""
  -- Menú principal ---------------------
  Base de datos activa: {db_label}
  ---------------------------------------
    1. Administrar bases de datos
    2. Administrar colecciones / tablas
    3. Operaciones CRUD
    4. Consultas y agregaciones
    0. Salir
  ---------------------------------------""")

    # -- BASES DE DATOS

    def _menu_databases(self):
        print("""
  -- Bases de datos ---------------------
    1. Listar bases de datos
    2. Crear base de datos
    3. Eliminar base de datos
    4. Seleccionar base de datos activa
    0. Volver
  ---------------------------------------""")
        opt = input("  Opción: ").strip()

        if opt == "1":
            r = self.client.send_nosql({"op": "list_dbs"}, self.session)
            self._print_list("Bases de datos", r.get("databases", []), r)

        elif opt == "2":
            name = _ask("Nombre de la nueva base de datos")
            if name:
                r = self.client.send_nosql({"op": "create_db", "db": name}, self.session)
                self._print_status(r)

        elif opt == "3":
            name = _ask("Nombre de la base de datos a eliminar")
            if name and _confirm(f"¿Eliminar '{name}'? Esta acción no se puede deshacer"):
                r = self.client.send_nosql({"op": "drop_db", "db": name}, self.session)
                self._print_status(r)

        elif opt == "4":
            name = _ask("Nombre de la base de datos")
            if name:
                self.active_db = name
                print(f"\n  ✓ Base de datos activa: {self.active_db}\n")

    # -- COLECCIONES

    def _menu_collections(self):
        if not self._check_db():
            return
        print("""
  -- Colecciones ------------------------
    1. Listar colecciones
    2. Crear colección
    3. Eliminar colección
    0. Volver
  ---------------------------------------""")
        opt = input("  Opción: ").strip()

        if opt == "1":
            r = self.client.send_nosql(
                {"op": "list_tables", "db": self.active_db}, self.session
            )
            self._print_list("Colecciones", r.get("tables", []), r)

        elif opt == "2":
            name = _ask("Nombre de la colección")
            if name:
                r = self.client.send_nosql(
                    {"op": "create_table", "db": self.active_db,
                     "collection": name, "mode": "collection"},
                    self.session,
                )
                self._print_status(r)

        elif opt == "3":
            name = _ask("Nombre de la colección a eliminar")
            if name and _confirm(f"¿Eliminar colección '{name}'?"):
                r = self.client.send_nosql(
                    {"op": "drop_table", "db": self.active_db, "collection": name},
                    self.session,
                )
                self._print_status(r)

    # -- CRUD 

    def _menu_crud(self):
        if not self._check_db():
            return
        print("""
  -- Operaciones CRUD -------------------
    1. Buscar documentos
    2. Insertar documento
    3. Actualizar documentos
    4. Eliminar documentos
    0. Volver
  ---------------------------------------""")
        opt = input("  Opción: ").strip()

        if opt == "1":
            self._op_find()
        elif opt == "2":
            self._op_insert()
        elif opt == "3":
            self._op_update()
        elif opt == "4":
            self._op_delete()

    def _op_find(self):
        col    = _ask("Colección")
        fields = _ask_fields()
        filt   = _ask_filter()
        limit  = _ask_number("Límite de resultados (Enter para sin límite)")

        msg = {"op": "find", "db": self.active_db,
               "collection": col, "fields": fields, "filter": filt}
        if limit:
            msg["options"] = {"limit": limit}

        r = self.client.send_nosql(msg, self.session)
        self._print_documents(r)

    def _op_insert(self):
        col  = _ask("Colección")
        print("  Ingresa los campos del documento (Enter en nombre para terminar):")
        doc  = _ask_document()
        if not doc:
            print("  Documento vacío, operación cancelada.")
            return
        r = self.client.send_nosql(
            {"op": "insert", "db": self.active_db, "collection": col, "document": doc},
            self.session,
        )
        self._print_status(r)

    def _op_update(self):
        col  = _ask("Colección")
        print("  Condición para seleccionar documentos a actualizar:")
        filt = _ask_filter()
        print("  Nuevos valores:")
        data = _ask_document()
        if not data:
            return
        r = self.client.send_nosql(
            {"op": "update", "db": self.active_db, "collection": col,
             "filter": filt, "update": data},
            self.session,
        )
        self._print_status(r)

    def _op_delete(self):
        col  = _ask("Colección")
        print("  Condición para seleccionar documentos a eliminar:")
        filt = _ask_filter()
        if not filt:
            if not _confirm("¿Eliminar TODOS los documentos de la colección?"):
                return
        r = self.client.send_nosql(
            {"op": "delete", "db": self.active_db, "collection": col, "filter": filt},
            self.session,
        )
        self._print_status(r)

    # -- CONSULTAS Y AGREGACIONES 

    def _menu_queries(self):
        if not self._check_db():
            return
        print("""
  -- Consultas y agregaciones -----------
    1. Contar documentos   (COUNT)
    2. Sumar un campo      (SUM)
    3. Promedio de campo   (AVG)
    4. Valores únicos      (DISTINCT)
    5. Cruzar colecciones  (INNER JOIN)
    0. Volver
  ---------------------------------------""")
        opt = input("  Opción: ").strip()

        if opt in ("1", "2", "3"):
            ops  = {"1": "count", "2": "sum", "3": "avg"}
            col  = _ask("Colección")
            field = _ask("Campo a calcular (* para COUNT)") if opt == "1" else _ask("Campo numérico")
            filt = _ask_filter()
            r = self.client.send_nosql(
                {"op": ops[opt], "db": self.active_db,
                 "collection": col, "field": field, "filter": filt},
                self.session,
            )
            label = {"1": "COUNT", "2": "SUM", "3": "AVG"}[opt]
            if r["success"]:
                print(f"\n  {label}: {r.get('value')}\n")
            else:
                print(f"\n  ✗ {r['message']}\n")

        elif opt == "4":
            col   = _ask("Colección")
            field = _ask("Campo del que quieres valores únicos")
            filt  = _ask_filter()
            r = self.client.send_nosql(
                {"op": "distinct", "db": self.active_db,
                 "collection": col, "field": field, "filter": filt},
                self.session,
            )
            if r["success"]:
                print(f"\n  Valores únicos: {', '.join(str(v) for v in r.get('values', []))}\n")
            else:
                print(f"\n  ✗ {r['message']}\n")

        elif opt == "5":
            col_a  = _ask("Colección principal")
            col_b  = _ask("Colección a cruzar")
            on     = _ask(f"Condición (ej: {col_a}.id = {col_b}.fk)")
            fields = _ask_fields()
            filt   = _ask_filter()
            r = self.client.send_nosql(
                {"op": "join", "db": self.active_db, "collection": col_a,
                 "join_collection": col_b, "on": on,
                 "fields": fields, "filter": filt},
                self.session,
            )
            self._print_documents(r)

    # -- Presentación

    def _print_status(self, r: dict):
        if r["success"]:
            print(f"\n  ✓ {r.get('message', 'OK')}\n")
        else:
            print(f"\n  ✗ {r.get('message', 'Error desconocido')}\n")

    def _print_list(self, label: str, items: list, r: dict):
        if not r["success"]:
            print(f"\n  ✗ {r['message']}\n")
            return
        if not items:
            print(f"\n  (sin {label.lower()})\n")
            return
        print(f"\n  {label}:")
        for item in items:
            print(f"    • {item}")
        print()

    def _print_documents(self, r: dict):
        if not r["success"]:
            print(f"\n  ✗ {r['message']}\n")
            return
        docs = r.get("documents", [])
        if not docs:
            print("\n  Sin resultados.\n")
            return
        print(f"\n  {len(docs)} resultado(s):")
        for doc in docs:
            pairs = "  ".join(f"{k}: {v}" for k, v in doc.items())
            print(f"    {{ {pairs} }}")
        print()

    def _check_db(self) -> bool:
        if not self.active_db:
            print("\n  ✗ Primero selecciona una base de datos (menú → Administrar bases de datos → opción 4)\n")
            return False
        return True

    def _banner(self):
        print(f"""
  
     Modo NoSQL — menú guiado           
     Usuario: {self.session['username']:<26}
     Rol:     {self.session['role']:<26}
  """)


# -- Helpers de entrada 

def _ask(label: str) -> str:
    return input(f"  {label}: ").strip()

def _confirm(msg: str) -> bool:
    return input(f"  {msg} [s/N]: ").strip().lower() == "s"

def _ask_number(label: str) -> int | None:
    val = input(f"  {label}: ").strip()
    try:
        return int(val) if val else None
    except ValueError:
        return None

def _ask_fields() -> list:
    raw = input("  Campos a mostrar (separados por coma, Enter para todos): ").strip()
    if not raw:
        return ["*"]
    return [f.strip() for f in raw.split(",")]

def _ask_filter() -> dict:
    """Pide condiciones de filtro campo por campo."""
    print("  Filtro (Enter en campo para no filtrar):")
    ops_display = "  ($eq igual  $gt mayor  $lt menor  $gte mayor-igual  $lte menor-igual  $ne distinto)"
    print(ops_display)

    result = {}
    while True:
        field = input("    Campo: ").strip()
        if not field:
            break
        op  = input("    Operador: ").strip() or "$eq"
        val = input("    Valor: ").strip()

        # intenta convertir a número
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass

        result[field] = {op: val}

        if input("  ¿Agregar otra condición? [s/N]: ").strip().lower() != "s":
            break

    return result

def _ask_document() -> dict:
    """Pide campos de un documento uno por uno."""
    doc = {}
    while True:
        key = input("    Campo: ").strip()
        if not key:
            break
        val = input("    Valor: ").strip()
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass
        doc[key] = val
    return doc