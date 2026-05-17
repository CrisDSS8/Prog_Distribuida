"""
Componente 8: Acceso a Archivos
Responsabilidad:
  - Interactua con el sistema de archivos local.
  - Leer archivos, escribir archivos, obtener metadatos, detectar cambios.
"""

import os

DIRECTORIO_BASE = "./compartidos"
REPO_TEMPORAL   = "./temp_repo"


def inicializar_directorios() -> None:
    os.makedirs(DIRECTORIO_BASE, exist_ok=True)
    os.makedirs(REPO_TEMPORAL,   exist_ok=True)


def obtener_atributos(nombre: str, carpeta: str = DIRECTORIO_BASE) -> dict | None:
    ruta = os.path.join(carpeta, nombre)
    if not os.path.exists(ruta):
        return None
    st = os.stat(ruta)
    _, ext = os.path.splitext(nombre)
    return {
        "nombre":    nombre,
        "extension": ext,
        "size":      st.st_size,
        "ctime":     st.st_ctime,
        "mtime":     st.st_mtime,
        "ttl":       0,
    }


def leer_archivo(nombre: str, carpeta: str = DIRECTORIO_BASE) -> str | None:
    ruta = os.path.join(carpeta, nombre)
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()


def escribir_archivo(nombre: str, contenido: str,
                     carpeta: str = DIRECTORIO_BASE) -> None:
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)


def existe_local(nombre: str, carpeta: str = DIRECTORIO_BASE) -> bool:
    return os.path.exists(os.path.join(carpeta, nombre))


def eliminar_archivo(nombre: str, carpeta: str = DIRECTORIO_BASE) -> bool:
    """Elimina un archivo del directorio indicado. Retorna True si existia."""
    ruta = os.path.join(carpeta, nombre)
    if os.path.exists(ruta):
        os.remove(ruta)
        return True
    return False


def eliminar_copia_temporal(nombre: str) -> bool:
    """Elimina la copia temporal de un archivo en temp_repo."""
    ruta = os.path.join(REPO_TEMPORAL, nombre)
    if os.path.exists(ruta):
        os.remove(ruta)
        return True
    return False


def listar_archivos_locales() -> list:
    if not os.path.exists(DIRECTORIO_BASE):
        return []
    return [
        f for f in os.listdir(DIRECTORIO_BASE)
        if os.path.isfile(os.path.join(DIRECTORIO_BASE, f))
    ]


def timestamp_modificacion(nombre: str,
                            carpeta: str = DIRECTORIO_BASE) -> float:
    ruta = os.path.join(carpeta, nombre)
    if not os.path.exists(ruta):
        return 0.0
    return os.path.getmtime(ruta)