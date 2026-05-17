"""
servidor.py  —  Orquestador principal
Responsabilidad unica: recibir mensajes UDP y delegar cada tipo
de flag al componente correspondiente.
NO contiene logica de negocio propia.

CAMBIOS respecto a version anterior:
  - Import de encriptador
  - Llamada a encriptador.iniciar_intercambio() en servidor_main()
  - Log de estado del cifrado al arrancar
  - Soporte de fragmentacion para archivos grandes (REQ_USE / SYNC_BACK)
"""

import socket
import threading
import json
from protocolo import crear_paquete, desempaquetar, BUFFER_SIZE

from componentes import comunicacion
from componentes import directorio
from componentes import acceso_archivos
from componentes import repositorio
from componentes import sincronizador
from componentes import ttl_manager
from componentes import logger
from componentes import encriptador          # ★ cifrado

# --------------------------------------------------
#  CONFIGURACION - ajusta antes de ejecutar
# --------------------------------------------------
OTROS_SERVIDORES = ["172.26.161.173", "172.26.166.23", "172.26.166.207"]   # IPs de los demas servidores
# --------------------------------------------------


def manejar_mensaje(sock: socket.socket, addr: tuple, paquete: dict) -> None:
    flags  = paquete.get("flags", "")
    trace  = paquete.get("trace_id", "???")
    data   = paquete.get("data",  "")
    mi_ip  = comunicacion.obtener_ip_local()

    if flags == "REQ_LIST":
        lista = directorio.listar_todo()
        comunicacion.enviar_respuesta(
            sock, addr, "RES_LIST", json.dumps(lista), trace
        )
        logger.registrar(f"REQ_LIST -> {addr[0]} ({len(lista)} archivos)", trace)

    elif flags == "REQ_INFO":
        info = directorio.buscar(data)
        if info and info.get("autoritativo"):
            comunicacion.enviar_respuesta(
                sock, addr, "RES_AUTH", json.dumps(info["stats"]), trace
            )
            logger.registrar(f"REQ_INFO AUTH: {data} -> {addr[0]}", trace)
        elif info:
            comunicacion.enviar_respuesta(
                sock, addr, "RES_NON_AUTH", info["owner"], trace
            )
            logger.registrar(
                f"REQ_INFO NON_AUTH: {data} dueno={info['owner']} -> {addr[0]}",
                trace
            )
        else:
            comunicacion.enviar_respuesta(sock, addr, "NACK", "", trace)
            logger.registrar(f"REQ_INFO NACK: {data}", trace)

    elif flags == "PUBLISH":
        try:
            attrs = json.loads(data)
            sincronizador.recibir_publish(attrs, ip_origen=addr[0],
                                          trace_id=trace)
        except Exception as e:
            logger.registrar(f"PUBLISH error: {e}", trace)

    elif flags == "REQ_USE":
        nombre = data

        if acceso_archivos.existe_local(nombre):
            repositorio.registrar_prestamo(nombre, addr[0], via_repo=False)
            contenido = acceso_archivos.leer_archivo(nombre)
            respuesta = {
                "attrs":     acceso_archivos.obtener_atributos(nombre),
                "contenido": contenido
            }
            # ★ usar enviar_fragmentado para soportar archivos grandes
            comunicacion.enviar_fragmentado(
                sock, addr, "RES_AUTH", json.dumps(respuesta), trace
            )
            logger.registrar(f"REQ_USE AUTH (dueno): {nombre} -> {addr[0]}", trace)

        else:
            info = directorio.buscar(nombre)
            if info:
                ip_dueno = info["owner"]
                logger.registrar(
                    f"REQ_USE REPO: solicitando copia de {nombre} al dueno {ip_dueno}",
                    trace
                )
                copia = repositorio.obtener_copia_de_dueno(nombre, ip_dueno, trace)
                if copia:
                    repositorio.registrar_prestamo(nombre, addr[0], via_repo=True)
                    # ★ usar enviar_fragmentado para soportar archivos grandes
                    comunicacion.enviar_fragmentado(
                        sock, addr, "RES_AUTH", json.dumps(copia), trace
                    )
                    logger.registrar(
                        f"REQ_USE REPO entregado: {nombre} -> {addr[0]}", trace
                    )
                else:
                    comunicacion.enviar_respuesta(
                        sock, addr, "NACK", "No se pudo obtener copia", trace
                    )
            else:
                comunicacion.enviar_respuesta(sock, addr, "NACK", "", trace)
                logger.registrar(f"REQ_USE NACK: {nombre} no registrado", trace)

    elif flags == "SYNC_BACK":
        try:
            datos = json.loads(data)
            repositorio.procesar_sync_back(datos, mi_ip, trace_id=trace)
        except Exception as e:
            logger.registrar(f"SYNC_BACK error: {e}", trace)

    # ── REQ_DELETE: cliente solicita eliminar un archivo ──────────────────
    elif flags == "REQ_DELETE":
        nombre     = data
        ip_cliente = addr[0]

        if not acceso_archivos.existe_local(nombre):
            comunicacion.enviar_respuesta(sock, addr, "NACK",
                                          "Este servidor no es el dueno del archivo", trace)
            logger.registrar(
                f"REQ_DELETE NACK (no propietario): {nombre} <- {ip_cliente}", trace)

        elif ip_cliente != mi_ip:
            comunicacion.enviar_respuesta(sock, addr, "NACK",
                                          f"Solo el propietario ({mi_ip}) puede eliminar este archivo", trace)
            logger.registrar(
                f"REQ_DELETE DENEGADO: {nombre} solicitado por {ip_cliente}, "
                f"propietario es {mi_ip}", trace)

        elif directorio.esta_bloqueado(nombre):
            usuarios = directorio.quien_bloquea(nombre)
            comunicacion.enviar_respuesta(sock, addr, "NACK",
                                          f"Archivo en uso por: {', '.join(usuarios)}", trace)
            logger.registrar(
                f"REQ_DELETE BLOQUEADO: {nombre} en uso por {usuarios}", trace)

        else:
            acceso_archivos.eliminar_archivo(nombre)
            directorio.eliminar_forzado(nombre)

            pkt_notify = crear_paquete(0, 0, "FILE_DELETED", nombre, trace)
            for ip in OTROS_SERVIDORES:
                comunicacion.enviar_udp(ip, pkt_notify)

            comunicacion.enviar_respuesta(sock, addr, "ACK", nombre, trace)
            logger.registrar(
                f"REQ_DELETE OK: {nombre} eliminado por {ip_cliente}, notificado a red", trace)

    # ── FILE_DELETED: otro servidor elimino un archivo ────────────────────
    elif flags == "FILE_DELETED":
        nombre = data
        directorio.eliminar_forzado(nombre)
        acceso_archivos.eliminar_copia_temporal(nombre)
        logger.registrar(
            f"FILE_DELETED: registro de {nombre} eliminado (notif. remota)", trace)

    # ── FILE_LOCK ─────────────────────────────────────────────────────────
    elif flags == "FILE_LOCK":
        try:
            payload    = json.loads(data)
            nombre     = payload["nombre"]
            ip_usuario = payload["ip_usuario"]
            directorio.bloquear(nombre, ip_usuario)
            logger.registrar(f"FILE_LOCK: {nombre} bloqueado por {ip_usuario}", trace)
        except Exception as e:
            logger.registrar(f"FILE_LOCK error: {e}", trace)

    # ── FILE_UNLOCK ───────────────────────────────────────────────────────
    elif flags == "FILE_UNLOCK":
        try:
            payload    = json.loads(data)
            nombre     = payload["nombre"]
            ip_usuario = payload["ip_usuario"]
            directorio.desbloquear(nombre, ip_usuario)
            logger.registrar(f"FILE_UNLOCK: {nombre} desbloqueado por {ip_usuario}", trace)
        except Exception as e:
            logger.registrar(f"FILE_UNLOCK error: {e}", trace)

    elif flags == "STALE_RECORD":
        nombre = data
        if directorio.esta_bloqueado(nombre):
            logger.registrar(
                f"STALE_RECORD ignorado: {nombre} esta en uso actualmente", trace)
        elif directorio.eliminar(nombre):
            logger.registrar(
                f"STALE_RECORD: {nombre} eliminado (registro desactualizado)", trace)
        else:
            logger.registrar(f"STALE_RECORD: {nombre} ya no estaba en registro", trace)

    elif flags == "REQ_LOG":
        contenido_log = logger.obtener_ultimas_lineas(200)
        comunicacion.enviar_respuesta(sock, addr, "RES_LOG", contenido_log, trace)
        logger.registrar(f"REQ_LOG -> {addr[0]}", trace)

    elif flags == "FORCE_PUBLISH":
        threading.Thread(
            target=sincronizador.publicar_archivos_locales, daemon=True
        ).start()
        logger.registrar("FORCE_PUBLISH recibido -> re-publicando", trace)

    else:
        logger.registrar(f"Flag desconocido: {flags} desde {addr}", trace)


def servidor_main() -> None:
    acceso_archivos.inicializar_directorios()

    sincronizador.configurar(OTROS_SERVIDORES)
    ttl_manager.configurar(OTROS_SERVIDORES)

    logger.registrar("Iniciando intercambio de claves con peers...")
    encriptador.iniciar_intercambio(OTROS_SERVIDORES)
    estado_cifrado = "Fernet/AES activo" if encriptador.esta_activo() else "SIN CIFRADO (modo degradado)"
    logger.registrar(f"Estado de cifrado: {estado_cifrado}")

    threading.Thread(
        target=sincronizador.publicar_archivos_locales, daemon=True
    ).start()
    ttl_manager.iniciar_hilo()
    sincronizador.iniciar_hilo_anuncio()
    repositorio.iniciar_limpieza_temporal()

    server_sock = comunicacion.crear_socket_servidor()
    logger.registrar(
        f"Servidor activo en puerto {comunicacion.PUERTO_NET}  "
        f"IP={comunicacion.obtener_ip_local()}  "
        f"Cifrado=[{estado_cifrado}]"
    )

    while True:
        try:
            raw, addr = server_sock.recvfrom(BUFFER_SIZE)
            pkt = desempaquetar(raw)
            if pkt:
                # ★ Si llega un CHUNK_START, acumular todos los fragmentos
                # antes de despachar al manejador
                flag = pkt.get("flags", "")
                if flag in ("CHUNK_START", "CHUNK", "CHUNK_END"):
                    threading.Thread(
                        target=_recibir_y_manejar_fragmentado,
                        args=(server_sock, addr, pkt),
                        daemon=True
                    ).start()
                else:
                    threading.Thread(
                        target=manejar_mensaje,
                        args=(server_sock, addr, pkt),
                        daemon=True
                    ).start()
        except Exception as e:
            logger.registrar(f"Error en loop principal: {e}")


def _recibir_y_manejar_fragmentado(sock: socket.socket,
                                    addr: tuple, primer_pkt: dict) -> None:
    """
    Ensambla un mensaje fragmentado entrante y lo despacha a manejar_mensaje.
    Se lanza en un hilo separado para no bloquear el loop principal.
    """
    import json as _json

    fragmentos: dict = {}
    total_esperado   = 0
    flag_real        = ""
    trace_id         = ""
    last_ts          = 0.0

    def procesar_fragmento(pkt: dict) -> bool:
        """Agrega el fragmento al buffer. Retorna True cuando estan todos."""
        nonlocal total_esperado, flag_real, trace_id, last_ts
        try:
            meta = _json.loads(pkt["data"])
        except Exception:
            return False
        fragmentos[meta["seq"]] = meta["data_chunk"]
        total_esperado          = meta["total"]
        flag_real               = meta["flag_real"]
        trace_id                = pkt.get("trace_id", "")
        last_ts                 = pkt.get("timestamp", 0.0)
        return len(fragmentos) == total_esperado

    # Procesar el primer fragmento ya recibido
    if procesar_fragmento(primer_pkt):
        pass  # era el unico (raro, pero posible con total=1)
    else:
        # Esperar el resto de fragmentos del mismo trace
        sock.settimeout(10.0)
        while len(fragmentos) < total_esperado:
            try:
                raw, _ = sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                logger.registrar(
                    f"FRAGMENTO TIMEOUT: trace={trace_id} "
                    f"recibidos={len(fragmentos)}/{total_esperado}")
                return
            pkt = desempaquetar(raw)
            if not pkt:
                continue
            f = pkt.get("flags", "")
            if f in ("CHUNK_START", "CHUNK", "CHUNK_END"):
                procesar_fragmento(pkt)
            else:
                # Paquete de otro cliente llegado mientras esperabamos:
                # lo despachamos en su propio hilo y seguimos esperando
                threading.Thread(
                    target=manejar_mensaje,
                    args=(sock, addr, pkt),
                    daemon=True
                ).start()

    # Reconstruir el mensaje completo
    if not all(i in fragmentos for i in range(total_esperado)):
        logger.registrar(f"FRAGMENTO INCOMPLETO: trace={trace_id}")
        return

    data_completa = "".join(fragmentos[i] for i in range(total_esperado))
    paquete_completo = {
        "flags":     flag_real,
        "data":      data_completa,
        "trace_id":  trace_id,
        "seq":       0,
        "ack":       0,
        "timestamp": last_ts,
    }
    manejar_mensaje(sock, addr, paquete_completo)


if __name__ == "__main__":
    servidor_main()