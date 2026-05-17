"""
Componente 4: TTL Manager
Responsabilidad:
  - Verificar periodicamente archivos con TTL > 0.
  - Preguntar a otros servidores si siguen disponibles.
  - Eliminar o actualizar registros segun la respuesta.
  - TTL = 0 significa archivo propio permanente: nunca se toca.
"""

import time
import threading
from protocolo import crear_paquete
from componentes import directorio, comunicacion, logger

INTERVALO_TTL    = 30   # segundos entre verificaciones
OTROS_SERVIDORES: list = []   # se inyecta desde servidor.py


def configurar(otros_servidores: list) -> None:
    """Inyecta la lista de IPs de los demas servidores."""
    global OTROS_SERVIDORES
    OTROS_SERVIDORES = otros_servidores


def _verificar_ciclo() -> None:
    """Logica de un ciclo completo de verificacion TTL."""
    logger.registrar("=== Verificacion TTL iniciada ===")
    entradas = directorio.obtener_entradas_con_ttl()

    for nombre, info in entradas:
        encontrado_en = None

        for ip in OTROS_SERVIDORES:
            pkt  = crear_paquete(0, 0, "REQ_INFO", nombre)
            resp = comunicacion.enviar_y_esperar(ip, pkt)
            if resp and resp.get("flags") == "RES_AUTH":
                encontrado_en = ip
                break

        # Verificar que el registro aun existe antes de modificar
        actual = directorio.buscar(nombre)
        if actual is None:
            continue

        if encontrado_en:
            if actual.get("owner") != encontrado_en:
                directorio.actualizar_dueno(nombre, encontrado_en)
                logger.registrar(f"TTL UPDATE: {nombre} -> nuevo dueno {encontrado_en}")
        else:
            directorio.eliminar(nombre)
            logger.registrar(
                f"TTL EXPIRED: {nombre} eliminado "
                f"(ningun servidor lo confirmo)"
            )


def iniciar_hilo() -> threading.Thread:
    """Lanza el hilo daemon de verificacion periodica de TTL."""
    def loop():
        while True:
            time.sleep(INTERVALO_TTL)
            _verificar_ciclo()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
