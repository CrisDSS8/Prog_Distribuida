"""
Componente 7: Repositorio (Politica de copia)
"""

import time
import json
import threading
from protocolo import crear_paquete
from componentes import directorio, acceso_archivos, comunicacion, logger

_prestados: dict = {}
_lock = threading.Lock()

TIMEOUT_PRESTAMO = 300  # 5 minutos


# ── Unit of Work ───────────────────────────────────────────────────────────

def registrar_prestamo(nombre: str, ip_cliente: str,
                       via_repo: bool = False) -> None:
    """
    Marca un archivo como en uso.
    - via_repo=False  -> archivo propio: se bloquea con la IP del SERVIDOR
                         (no del cliente), porque el unlock lo hara el mismo
                         servidor al recibir SYNC_BACK o al liberar.
    - via_repo=True   -> archivo ajeno: se bloquea con la IP del cliente
                         intermediario, que mandara FILE_UNLOCK al terminar.
    """
    mi_ip = comunicacion.obtener_ip_local()

    # Para archivos propios usamos mi_ip como clave de bloqueo,
    # para ajenos usamos la IP del servidor intermediario que pide la copia.
    ip_bloqueo = mi_ip if not via_repo else ip_cliente

    with _lock:
        _prestados[nombre] = {
            "ip":         ip_cliente,
            "ip_bloqueo": ip_bloqueo,
            "timestamp":  time.time(),
            "via_repo":   via_repo,
        }
    directorio.bloquear(nombre, ip_bloqueo)


def liberar_prestamo(nombre: str) -> None:
    """Elimina el registro de prestamo y desbloquea en directorio."""
    with _lock:
        info = _prestados.pop(nombre, None)
    if info:
        directorio.desbloquear(nombre, info["ip_bloqueo"])


def esta_prestado(nombre: str) -> bool:
    with _lock:
        return nombre in _prestados


# ── Mensajes de bloqueo remoto ─────────────────────────────────────────────

def notificar_bloqueo(ip_dueno: str, nombre: str,
                      ip_usuario: str, trace_id: str = "") -> None:
    payload = json.dumps({"nombre": nombre, "ip_usuario": ip_usuario})
    pkt = crear_paquete(0, 0, "FILE_LOCK", payload, trace_id)
    comunicacion.enviar_udp(ip_dueno, pkt)
    logger.registrar(
        f"FILE_LOCK enviado a {ip_dueno}: {nombre} (usuario={ip_usuario})", trace_id)


def notificar_desbloqueo(ip_dueno: str, nombre: str,
                         ip_usuario: str, trace_id: str = "") -> None:
    payload = json.dumps({"nombre": nombre, "ip_usuario": ip_usuario})
    pkt = crear_paquete(0, 0, "FILE_UNLOCK", payload, trace_id)
    comunicacion.enviar_udp(ip_dueno, pkt)
    logger.registrar(
        f"FILE_UNLOCK enviado a {ip_dueno}: {nombre} (usuario={ip_usuario})", trace_id)


# ── Limpieza automatica de copias huerfanas ────────────────────────────────

def _hilo_limpieza_temporal() -> None:
    while True:
        time.sleep(60)
        ahora = time.time()
        expirados = []
        with _lock:
            for nombre, info in list(_prestados.items()):
                if info.get("via_repo") and (ahora - info["timestamp"]) > TIMEOUT_PRESTAMO:
                    expirados.append((nombre, info.copy()))

        for nombre, info in expirados:
            if acceso_archivos.eliminar_copia_temporal(nombre):
                logger.registrar(
                    f"REPO CLEANUP: copia temporal expirada: {nombre}")
            entrada = directorio.buscar(nombre)
            if entrada:
                notificar_desbloqueo(
                    entrada["owner"], nombre, info["ip_bloqueo"], trace_id="CLEANUP")
            liberar_prestamo(nombre)


def iniciar_limpieza_temporal() -> None:
    threading.Thread(target=_hilo_limpieza_temporal, daemon=True).start()


# ── Politica de repositorio (Cache-Aside) ─────────────────────────────────

def obtener_copia_de_dueno(nombre: str, ip_dueno: str,
                            trace_id: str = "") -> dict | None:
    mi_ip = comunicacion.obtener_ip_local()
    pkt   = crear_paquete(0, 0, "REQ_USE", nombre, trace_id)
    resp  = comunicacion.enviar_y_esperar(ip_dueno, pkt, timeout=5.0)

    if not resp or resp.get("flags") != "RES_AUTH":
        logger.registrar(
            f"REPO: No se pudo obtener copia de {nombre} desde {ip_dueno}", trace_id)
        return None

    datos = json.loads(resp["data"])
    acceso_archivos.escribir_archivo(
        nombre, datos.get("contenido", ""), carpeta=acceso_archivos.REPO_TEMPORAL)

    # Notificar al dueno que bloquee con nuestra IP de servidor
    notificar_bloqueo(ip_dueno, nombre, mi_ip, trace_id)

    logger.registrar(
        f"REPO: Copia de {nombre} guardada en temp (dueno={ip_dueno})", trace_id)
    return datos


# ── Sincronizacion (SYNC_BACK) ─────────────────────────────────────────────

def procesar_sync_back(datos: dict, mi_ip: str, trace_id: str = "") -> None:
    from componentes import sincronizador

    nombre    = datos["nombre"]
    ts_remoto = datos["mtime"]
    contenido = datos["contenido"]
    es_nuevo  = datos.get("nuevo", False)

    if es_nuevo and not acceso_archivos.existe_local(nombre):
        acceso_archivos.escribir_archivo(nombre, contenido)
        logger.registrar(f"NUEVO ARCHIVO: {nombre} creado en compartidos", trace_id)
        sincronizador.publicar_archivo_nuevo(nombre, trace_id)

    elif acceso_archivos.existe_local(nombre):
        ts_local = acceso_archivos.timestamp_modificacion(nombre)
        if ts_remoto > ts_local:
            acceso_archivos.escribir_archivo(nombre, contenido)
            attrs = acceso_archivos.obtener_atributos(nombre)
            directorio.actualizar_stats(nombre, attrs)
            logger.registrar(
                f"SYNC OK: {nombre} actualizado (timestamp remoto gana)", trace_id)
        else:
            logger.registrar(
                f"SYNC CONFLICTO: {nombre} no actualizado (timestamp local gana)", trace_id)
    else:
        entrada  = directorio.buscar(nombre)
        ip_dueno = entrada["owner"] if entrada else None
        if ip_dueno and ip_dueno != mi_ip:
            logger.registrar(
                f"SYNC REPO: {nombre} no es mio, reenviando a {ip_dueno}", trace_id)
            pkt = crear_paquete(0, 0, "SYNC_BACK", json.dumps(datos), trace_id)
            comunicacion.enviar_udp(ip_dueno, pkt)
        else:
            logger.registrar(
                f"SYNC REPO: {nombre} sin dueno conocido, descarto", trace_id)

    # Notificar desbloqueo al dueno si era un archivo prestado (via_repo)
    with _lock:
        info = _prestados.get(nombre)
    if info and info.get("via_repo"):
        entrada = directorio.buscar(nombre)
        if entrada and entrada["owner"] != mi_ip:
            notificar_desbloqueo(
                entrada["owner"], nombre, info["ip_bloqueo"], trace_id)

    if acceso_archivos.eliminar_copia_temporal(nombre):
        logger.registrar(f"SYNC: copia temporal de {nombre} eliminada", trace_id)
    liberar_prestamo(nombre)