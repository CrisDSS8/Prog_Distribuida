"""
Componente 2: Comunicacion
Responsabilidad:
  - Toda la red: maneja sockets, envia y recibe mensajes.
  - Recibir REQUEST, enviar RESPONSE, manejar ACK / NACK.
  - Comunicacion entre servidores (UDP).
  - Fragmentacion automatica para archivos grandes (> CHUNK_SIZE bytes).
"""

import json
import math
import socket
from protocolo import crear_paquete, desempaquetar, BUFFER_SIZE

PUERTO_NET = 12000
CHUNK_SIZE = 30000   # bytes de contenido util por fragmento (seguro con cifrado Fernet)


def obtener_ip_local() -> str:
    """Detecta la IP local de este nodo."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def enviar_udp(ip: str, paquete: bytes) -> None:
    """Envia un datagrama UDP sin esperar respuesta (fire-and-forget)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(paquete, (ip, PUERTO_NET))
        s.close()
    except Exception:
        pass


def enviar_y_esperar(ip: str, paquete: bytes, timeout: float = 3.0):
    """
    Envia un datagrama UDP y espera la respuesta (request-reply).
    Soporta respuestas fragmentadas (CHUNK_START / CHUNK / CHUNK_END).
    Retorna el paquete deserializado o None si hay timeout/error.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(paquete, (ip, PUERTO_NET))
        resultado = recibir_fragmentado(s, timeout=timeout)
        s.close()
        return resultado
    except Exception:
        return None


def enviar_respuesta(sock: socket.socket, addr: tuple, flags: str,
                     data: str = "", trace_id: str = "") -> None:
    """
    Envia una respuesta al remitente.
    Si data supera CHUNK_SIZE la fragmenta automaticamente.
    """
    enviar_fragmentado(sock, addr, flags, data, trace_id)


def enviar_fragmentado(sock: socket.socket, addr: tuple,
                       flags: str, data: str, trace_id: str = "") -> None:
    """
    Envia data como uno o varios datagramas UDP.
    - Si cabe en un paquete → lo envia directo (comportamiento original).
    - Si no cabe → lo parte en chunks de CHUNK_SIZE bytes numerados.

    Flags especiales de fragmentacion:
      CHUNK_START  — primer fragmento
      CHUNK        — fragmento intermedio
      CHUNK_END    — ultimo fragmento
    Cada fragmento lleva en 'data' un JSON con:
      { flag_real, seq, total, data_chunk }
    """
    data_bytes = data.encode("utf-8")

    if len(data_bytes) <= CHUNK_SIZE:
        # Caso normal: un solo paquete
        pkt = crear_paquete(0, 0, flags, data, trace_id)
        sock.sendto(pkt, addr)
        return

    # Fragmentar
    total = math.ceil(len(data_bytes) / CHUNK_SIZE)
    for i in range(total):
        chunk = data_bytes[i * CHUNK_SIZE: (i + 1) * CHUNK_SIZE]

        if i == 0:
            chunk_flag = "CHUNK_START"
        elif i == total - 1:
            chunk_flag = "CHUNK_END"
        else:
            chunk_flag = "CHUNK"

        meta = json.dumps({
            "flag_real":  flags,
            "seq":        i,
            "total":      total,
            "data_chunk": chunk.decode("utf-8", errors="replace"),
        })
        pkt = crear_paquete(0, 0, chunk_flag, meta, trace_id)
        sock.sendto(pkt, addr)


def recibir_fragmentado(sock: socket.socket, timeout: float = 10.0) -> dict | None:
    """
    Recibe uno o varios datagramas y los ensambla si son fragmentos.

    - Paquete normal (flag distinto de CHUNK_*) → lo devuelve directo.
    - Fragmentos (CHUNK_START / CHUNK / CHUNK_END) → los acumula hasta
      tener todos y devuelve un unico dict con el flag y data originales.

    Retorna None en caso de timeout o error.
    """
    fragmentos: dict      = {}
    total_esperado: int   = 0
    flag_real: str        = ""
    trace_id: str         = ""
    last_ts: float        = 0.0

    sock.settimeout(timeout)

    while True:
        try:
            raw, _ = sock.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            return None

        pkt = desempaquetar(raw)
        if not pkt:
            return None

        flag = pkt.get("flags", "")

        # ── Paquete normal (no fragmentado) ───────────────────────────────
        if flag not in ("CHUNK_START", "CHUNK", "CHUNK_END"):
            return pkt

        # ── Es un fragmento ───────────────────────────────────────────────
        try:
            meta = json.loads(pkt["data"])
        except Exception:
            return None

        seq            = meta["seq"]
        total_esperado = meta["total"]
        flag_real      = meta["flag_real"]
        trace_id       = pkt.get("trace_id", "")
        last_ts        = pkt.get("timestamp", 0.0)
        fragmentos[seq] = meta["data_chunk"]

        # Verificar si ya tenemos todos los fragmentos
        if flag == "CHUNK_END" or len(fragmentos) == total_esperado:
            # Comprobar que no falte ninguno
            if all(i in fragmentos for i in range(total_esperado)):
                data_completa = "".join(fragmentos[i] for i in range(total_esperado))
                return {
                    "flags":     flag_real,
                    "data":      data_completa,
                    "trace_id":  trace_id,
                    "seq":       0,
                    "ack":       0,
                    "timestamp": last_ts,
                }
            # Faltan fragmentos: seguir esperando (el bucle continua)


def crear_socket_servidor() -> socket.socket:
    """Crea y vincula el socket UDP principal del servidor."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", PUERTO_NET))
    return s