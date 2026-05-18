"""
encriptador.py  —  Componente de seguridad en tránsito
=======================================================
Diseño: clave Fernet COMPARTIDA para toda la red.

Flujo en el SERVIDOR (al arrancar):
  1. Si existe clave.key local  → la carga y la usa
  2. Si NO existe               → la genera y la guarda en clave.key
  3. Intenta enviar la clave a los otros servidores (KEY_SYNC)
     para que todos terminen con el mismo clave.key

Flujo en el CLIENTE (al arrancar):
  1. Lee clave.key del mismo directorio
  2. Si no existe, espera hasta 10 s a que el servidor local la cree
  3. Con esa clave ya puede cifrar/descifrar igual que el servidor

Resultado: servidor y cliente en la misma máquina comparten
automáticamente la misma clave sin configuración manual.
"""

import os
import json
import time
import socket
import threading
import logging

# ── Dependencias opcionales ────────────────────────────────────────────────
try:
    from cryptography.fernet import Fernet
    CRYPTO_DISPONIBLE = True
except ImportError:
    CRYPTO_DISPONIBLE = False
    logging.warning(
        "[encriptador] 'cryptography' no instalada.\n"
        "Ejecuta: pip install cryptography\n"
        "El sistema arrancará en modo SIN CIFRADO."
    )

# ── Constantes ─────────────────────────────────────────────────────────────
ARCHIVO_CLAVE  = "clave.key"     # mismo directorio de trabajo
PUERTO_KEYEX   = 12001           # puerto dedicado a sincronización de clave
FLAG_KEY_SYNC  = "KEY_SYNC"      # servidor envía su clave a los peers
FLAG_KEY_ACK   = "KEY_SYNC_ACK"  # peer confirma recepción

# ── Estado interno ─────────────────────────────────────────────────────────
_fernet = None
_lock   = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _guardar_clave(clave: bytes) -> None:
    with open(ARCHIVO_CLAVE, "wb") as f:
        f.write(clave)
    logging.info(f"[encriptador] Clave guardada en {ARCHIVO_CLAVE}")


def _cargar_clave() -> bytes | None:
    if os.path.exists(ARCHIVO_CLAVE):
        with open(ARCHIVO_CLAVE, "rb") as f:
            return f.read().strip()
    return None


def _enviar_clave_a_peer(ip: str, clave: bytes) -> bool:
    """Envía la clave Fernet en texto a un peer por UDP (puerto KEYEX)."""
    try:
        payload = json.dumps({
            "flag":  FLAG_KEY_SYNC,
            "clave": clave.decode("utf-8"),
        }).encode("utf-8")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3.0)
        s.sendto(payload, (ip, PUERTO_KEYEX))
        # Esperar ACK
        try:
            data, _ = s.recvfrom(1024)
            pkt = json.loads(data.decode("utf-8"))
            return pkt.get("flag") == FLAG_KEY_ACK
        except Exception:
            return False
        finally:
            s.close()
    except Exception as e:
        logging.warning(f"[encriptador] Error enviando clave a {ip}: {e}")
        return False


def _hilo_recibir_clave(evento_listo: threading.Event) -> None:
    """
    Escucha en PUERTO_KEYEX por si un peer nos envía su clave
    (caso: este servidor arranca después que los demás).
    """
    global _fernet
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", PUERTO_KEYEX))
        sock.settimeout(12.0)
        data, addr = sock.recvfrom(65535)
        pkt = json.loads(data.decode("utf-8"))
        if pkt.get("flag") == FLAG_KEY_SYNC:
            clave = pkt["clave"].encode("utf-8")
            with _lock:
                _fernet = Fernet(clave)
            _guardar_clave(clave)
            logging.info(f"[encriptador] Clave recibida de {addr[0]} y guardada.")
            # Responder ACK
            ack = json.dumps({"flag": FLAG_KEY_ACK}).encode("utf-8")
            sock.sendto(ack, addr)
            evento_listo.set()
        sock.close()
    except Exception:
        pass  # timeout o error: el hilo principal maneja el fallback


# ══════════════════════════════════════════════════════════════════════════
#  API PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════

def iniciar_intercambio(peers: list) -> None:
    """
    Llamar desde servidor_main() antes de abrir el socket principal.

    Lógica:
      1. Si ya existe clave.key  → cargarla y usarla directamente.
      2. Si NO existe            → arrancar hilo que escucha si algún peer
                                   nos la envía (espera 5 s).
      3. Si nadie nos la envió   → generarla nosotros, guardarla y
                                   propagarla a los peers.
    """
    global _fernet

    if not CRYPTO_DISPONIBLE:
        logging.warning("[encriptador] Sin librería. Modo SIN CIFRADO.")
        return

    # ── Caso 1: ya tenemos la clave local ─────────────────────────────────
    clave_existente = _cargar_clave()
    if clave_existente:
        with _lock:
            _fernet = Fernet(clave_existente)
        logging.info("[encriptador] Clave cargada desde clave.key ✓")
        # Aun así propagamos a peers que puedan no tenerla todavia
        for ip in peers:
            threading.Thread(
                target=_enviar_clave_a_peer,
                args=(ip, clave_existente),
                daemon=True
            ).start()
        return

    # ── Caso 2: esperamos si algún peer nos la manda primero ──────────────
    evento = threading.Event()
    hilo   = threading.Thread(target=_hilo_recibir_clave, args=(evento,), daemon=True)
    hilo.start()
    evento.wait(timeout=5.0)   # esperar máximo 5 s

    with _lock:
        ya_tenemos = _fernet is not None

    if ya_tenemos:
        return   # el hilo receptor ya configuró todo

    # ── Caso 3: somos el primero → generamos y propagamos ─────────────────
    clave = Fernet.generate_key()
    with _lock:
        _fernet = Fernet(clave)
    _guardar_clave(clave)
    logging.info("[encriptador] Clave Fernet generada por este servidor.")

    for ip in peers:
        ok = _enviar_clave_a_peer(ip, clave)
        logging.info(
            f"[encriptador] Clave enviada a {ip}: {'OK' if ok else 'sin respuesta (reintentará al arrancar)'}"
        )


def cargar_para_cliente() -> None:
    """
    Llamar desde cliente.py al arrancar.
    Lee clave.key del mismo directorio (generado por el servidor local).
    Espera hasta 10 s si el servidor aún no la creó.
    """
    global _fernet

    if not CRYPTO_DISPONIBLE:
        logging.warning("[encriptador] Sin librería. Cliente en modo SIN CIFRADO.")
        return

    for intento in range(20):          # 20 x 0.5 s = 10 s máximo
        clave = _cargar_clave()
        if clave:
            with _lock:
                _fernet = Fernet(clave)
            logging.info("[encriptador] Cliente: clave cargada desde clave.key ✓")
            return
        time.sleep(0.5)

    logging.warning(
        "[encriptador] Cliente: no se encontró clave.key después de 10 s. "
        "Asegúrate de que el servidor local haya arrancado primero. "
        "Modo SIN CIFRADO activo."
    )


# ══════════════════════════════════════════════════════════════════════════
#  encrypt / decrypt  (usados por protocolo.py)
# ══════════════════════════════════════════════════════════════════════════

def encrypt(datos: bytes) -> bytes:
    """
    Cifra con Fernet si hay clave activa.
    Si no, devuelve los datos con prefijo PLAIN: (modo degradado).
    """
    with _lock:
        f = _fernet
    if f:
        return b"ENC:" + f.encrypt(datos)
    return b"PLAIN:" + datos


def decrypt(datos: bytes) -> bytes:
    """
    Descifra según el prefijo:
      ENC:   → descifrar con Fernet
      PLAIN: → devolver sin prefijo
      sin prefijo → compatibilidad con versiones anteriores
    """
    if datos.startswith(b"ENC:"):
        with _lock:
            f = _fernet
        if f:
            return f.decrypt(datos[4:])
        raise ValueError(
            "Paquete cifrado recibido pero no hay clave Fernet disponible. "
            "¿Arrancó el servidor local antes que el cliente?"
        )
    if datos.startswith(b"PLAIN:"):
        return datos[6:]
    # Compatibilidad: paquetes sin prefijo (versiones anteriores al cifrado)
    return datos


def esta_activo() -> bool:
    """True si el cifrado Fernet está listo para usarse."""
    with _lock:
        return _fernet is not None