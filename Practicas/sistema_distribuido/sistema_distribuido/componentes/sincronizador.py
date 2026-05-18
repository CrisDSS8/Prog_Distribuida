"""
Componente 6: Sincronizador
Responsabilidad:
  - Publicar nuevos archivos compartidos a otros nodos.
  - Recibir publicaciones autoritativas de otros servidores.
  - Sincronizar listas entre nodos (anuncio periodico).
  - Solo re-publica archivos que hayan cambiado desde el ultimo anuncio.
"""

import time
import json
import threading
from protocolo import crear_paquete
from componentes import directorio, acceso_archivos, comunicacion, logger

INTERVALO_ANUNCIO = 30
OTROS_SERVIDORES: list = []

# Guarda el ultimo mtime conocido de cada archivo para detectar cambios
_ultimo_mtime: dict = {}
_lock_mtime = threading.Lock()


def configurar(otros_servidores: list) -> None:
    """Inyecta la lista de IPs de los demas servidores."""
    global OTROS_SERVIDORES
    OTROS_SERVIDORES = otros_servidores


def publicar_archivos_locales() -> None:
    """
    Escanea ./compartidos, registra cada archivo como autoritativo
    y anuncia PUBLISH a todos los demas servidores.
    Se llama una sola vez al arrancar para registrar todo.
    """
    mi_ip    = comunicacion.obtener_ip_local()
    archivos = acceso_archivos.listar_archivos_locales()

    for nombre in archivos:
        attrs = acceso_archivos.obtener_atributos(nombre)
        if attrs:
            directorio.agregar(
                nombre, owner=mi_ip, stats=attrs,
                ttl=0, autoritativo=True
            )
            # Registrar mtime inicial para deteccion de cambios
            with _lock_mtime:
                _ultimo_mtime[nombre] = attrs.get("mtime", 0)

    for nombre in archivos:
        attrs = acceso_archivos.obtener_atributos(nombre)
        if not attrs:
            continue
        payload = {**attrs, "owner": mi_ip}
        pkt = crear_paquete(0, 0, "PUBLISH", json.dumps(payload))
        for ip in OTROS_SERVIDORES:
            comunicacion.enviar_udp(ip, pkt)

    logger.registrar(f"Publicados {len(archivos)} archivos (IP={mi_ip})")


def _verificar_y_publicar_cambios() -> None:
    """
    Revisa si algun archivo local cambio comparando mtime.
    Solo publica a la red los archivos que realmente cambiaron.
    No interrumpe a clientes que esten trabajando con otros archivos.
    """
    mi_ip    = comunicacion.obtener_ip_local()
    archivos = acceso_archivos.listar_archivos_locales()
    cambiados = []

    for nombre in archivos:
        attrs = acceso_archivos.obtener_atributos(nombre)
        if not attrs:
            continue

        mtime_actual = attrs.get("mtime", 0)

        with _lock_mtime:
            mtime_anterior = _ultimo_mtime.get(nombre, -1)
            es_nuevo   = mtime_anterior == -1
            fue_modificado = mtime_actual > mtime_anterior

        if es_nuevo or fue_modificado:
            cambiados.append((nombre, attrs))
            with _lock_mtime:
                _ultimo_mtime[nombre] = mtime_actual

            # Actualizar directorio local con datos frescos
            directorio.agregar(
                nombre, owner=mi_ip, stats=attrs,
                ttl=0, autoritativo=True
            )

    if not cambiados:
        logger.registrar("=== Verificacion TTL iniciada === Sin cambios detectados, no se re-publica")
        return

    # Solo publicar los archivos que cambiaron
    logger.registrar(
        f"=== Verificacion TTL iniciada === {len(cambiados)} archivo(s) cambiado(s), publicando..."
    )
    for nombre, attrs in cambiados:
        payload = {**attrs, "owner": mi_ip}
        pkt = crear_paquete(0, 0, "PUBLISH", json.dumps(payload))
        for ip in OTROS_SERVIDORES:
            comunicacion.enviar_udp(ip, pkt)
        logger.registrar(f"PUBLISH enviado por cambio: {nombre} (mtime actualizado)")


def publicar_archivo_nuevo(nombre: str, trace_id: str = "") -> None:
    """
    Registra un archivo recien creado como autoritativo
    y lo publica a la red.
    """
    mi_ip = comunicacion.obtener_ip_local()
    attrs = acceso_archivos.obtener_atributos(nombre)
    if not attrs:
        return

    directorio.agregar(nombre, owner=mi_ip, stats=attrs,
                       ttl=0, autoritativo=True)

    # Registrar mtime para que el hilo periodico no lo considere "nuevo"
    with _lock_mtime:
        _ultimo_mtime[nombre] = attrs.get("mtime", 0)

    payload = {**attrs, "owner": mi_ip}
    pkt     = crear_paquete(0, 0, "PUBLISH", json.dumps(payload), trace_id)
    for ip in OTROS_SERVIDORES:
        comunicacion.enviar_udp(ip, pkt)

    logger.registrar(f"NUEVO ARCHIVO publicado a la red: {nombre}", trace_id)


def recibir_publish(attrs: dict, ip_origen: str, trace_id: str = "") -> None:
    """
    Procesa un mensaje PUBLISH recibido de otro servidor:
    agrega o actualiza la entrada en el directorio local.
    """
    nombre = attrs.get("nombre", "")
    owner  = attrs.get("owner", ip_origen)
    directorio.agregar(
        nombre, owner=owner, stats=attrs,
        ttl=60, autoritativo=(owner == ip_origen)
    )
    logger.registrar(f"PUBLISH recibido: {nombre} (dueno={owner})", trace_id)


def iniciar_hilo_anuncio() -> threading.Thread:
    """
    Lanza el hilo daemon de verificacion periodica.
    Solo re-publica archivos que hayan cambiado desde el ultimo ciclo.
    Los clientes que esten trabajando con otros archivos no se ven afectados.
    """
    def loop():
        while True:
            time.sleep(INTERVALO_ANUNCIO)
            try:
                _verificar_y_publicar_cambios()
            except Exception as e:
                logger.registrar(f"Error en hilo de sincronizacion: {e}")

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t