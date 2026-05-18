"""
Componente 3: Directorio
Responsabilidad:
  - Mantiene la lista dinamica de archivos compartidos.
  - Cada entrada contiene: nombre, extension, tamano, fechas, dueno (IP), TTL.
  - Operaciones: agregar registros, actualizar dueno, eliminar registros,
    buscar archivos.
  - Sistema de bloqueo: un archivo en uso no puede eliminarse.
"""

import threading

# registro_global: nombre -> {owner, ttl, stats, autoritativo}
_registro: dict = {}
_lock = threading.Lock()

# bloqueos: nombre -> set de IPs que tienen el archivo en uso
_bloqueos: dict = {}
_lock_bloqueos = threading.Lock()


# ── Acceso al lock (para que otros componentes puedan usarlo) ──────────────
def get_lock() -> threading.Lock:
    return _lock


# ── Sistema de bloqueo ─────────────────────────────────────────────────────

def bloquear(nombre: str, ip_usuario: str) -> None:
    """Registra que ip_usuario esta usando el archivo nombre."""
    with _lock_bloqueos:
        if nombre not in _bloqueos:
            _bloqueos[nombre] = set()
        _bloqueos[nombre].add(ip_usuario)


def desbloquear(nombre: str, ip_usuario: str) -> None:
    """Libera el bloqueo de ip_usuario sobre el archivo nombre."""
    with _lock_bloqueos:
        if nombre in _bloqueos:
            _bloqueos[nombre].discard(ip_usuario)
            if not _bloqueos[nombre]:
                del _bloqueos[nombre]


def esta_bloqueado(nombre: str) -> bool:
    """Retorna True si algun cliente/servidor tiene el archivo en uso."""
    with _lock_bloqueos:
        return bool(_bloqueos.get(nombre))


def quien_bloquea(nombre: str) -> list:
    """Retorna la lista de IPs que tienen el archivo bloqueado."""
    with _lock_bloqueos:
        return list(_bloqueos.get(nombre, set()))


# ── Operaciones de escritura ───────────────────────────────────────────────

def agregar(nombre: str, owner: str, stats: dict,
            ttl: int = 60, autoritativo: bool = False) -> None:
    """Inserta o reemplaza un registro en el directorio."""
    with _lock:
        _registro[nombre] = {
            "owner":        owner,
            "ttl":          ttl,
            "stats":        stats,
            "autoritativo": autoritativo,
        }


def actualizar_dueno(nombre: str, nuevo_owner: str) -> bool:
    """Cambia el dueno de un registro existente. Retorna True si existia."""
    with _lock:
        if nombre not in _registro:
            return False
        _registro[nombre]["owner"]        = nuevo_owner
        _registro[nombre]["autoritativo"] = False
        return True


def actualizar_stats(nombre: str, stats: dict) -> None:
    """Actualiza los metadatos de un archivo ya registrado."""
    with _lock:
        if nombre in _registro:
            _registro[nombre]["stats"] = stats


def eliminar(nombre: str) -> bool:
    """
    Pruebadeeliminacion.txt un registro solo si no esta bloqueado.
    Retorna True si se elimino, False si no existia o esta en uso.
    """
    if esta_bloqueado(nombre):
        return False
    with _lock:
        if nombre in _registro:
            del _registro[nombre]
            return True
        return False


def eliminar_forzado(nombre: str) -> bool:
    """Pruebadeeliminacion.txt un registro ignorando bloqueos (solo para uso interno)."""
    with _lock:
        if nombre in _registro:
            del _registro[nombre]
            return True
        return False


# ── Operaciones de lectura ─────────────────────────────────────────────────

def buscar(nombre: str) -> dict | None:
    """Retorna una copia del registro o None si no existe."""
    with _lock:
        entrada = _registro.get(nombre)
        return dict(entrada) if entrada else None


def listar_todo() -> list:
    """Retorna una lista de dicts con los campos publicos de cada entrada."""
    with _lock_bloqueos:
        bloqueos_snap = {k: list(v) for k, v in _bloqueos.items()}
    with _lock:
        return [
            {
                "nombre":    k,
                "dueno":     v["owner"],
                "size":      v["stats"].get("size", 0),
                "mtime":     v["stats"].get("mtime", 0),
                "ttl":       v.get("ttl", 0),
                "en_uso":    bool(bloqueos_snap.get(k)),
            }
            for k, v in _registro.items()
        ]


def obtener_entradas_con_ttl() -> list:
    """Retorna pares (nombre, info) cuyo TTL > 0 para el hilo de verificacion."""
    with _lock:
        return [(k, dict(v)) for k, v in _registro.items() if v.get("ttl", 0) > 0]


def existe(nombre: str) -> bool:
    with _lock:
        return nombre in _registro