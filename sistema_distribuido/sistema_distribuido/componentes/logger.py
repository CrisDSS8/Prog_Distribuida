"""
Componente 9: Logger
Responsabilidad:
  - Registro obligatorio de eventos: altas, bajas, cambios de dueno,
    conflictos, errores y peticiones.
  - Devuelve las ultimas N lineas del log para visualizacion remota.
"""

import time

ARCHIVO_LOG = "servidor.log"


def registrar(mensaje: str, trace_id: str = "SYSTEM") -> None:
    """Escribe una entrada en el log local e imprime en consola."""
    ts   = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{trace_id}] {mensaje}\n"
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
    print(line.strip())


def obtener_ultimas_lineas(n: int = 200) -> str:
    """Retorna las ultimas N lineas del log como string."""
    try:
        with open(ARCHIVO_LOG, "r", encoding="latin-1") as f:
            lineas = f.readlines()
        ultimas = lineas[-n:] if len(lineas) > n else lineas
        return "".join(ultimas)
    except FileNotFoundError:
        return ""
