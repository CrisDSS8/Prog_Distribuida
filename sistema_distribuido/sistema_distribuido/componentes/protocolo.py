"""
protocolo.py  —  Serialización y cifrado de paquetes UDP
=========================================================
El cifrado es transparente: crear_paquete() cifra automáticamente
y desempaquetar() descifra automáticamente.

El resto del sistema (cliente, servidor, componentes) no necesita
ningún cambio adicional para aprovechar el cifrado.

Compatibilidad:
  - Paquetes sin prefijo ENC:/PLAIN: se tratan como texto plano
    (permite interoperabilidad con versiones anteriores del sistema).
"""

import json
import time
import uuid

# Importación del encriptador — si no existe el módulo o falla,
# el protocolo funciona igual que antes (sin cifrado).
try:
    from componentes import encriptador as _enc
    _CIFRADO_DISPONIBLE = True
except ImportError:
    try:
        import encriptador as _enc      # fallback: mismo directorio
        _CIFRADO_DISPONIBLE = True
    except ImportError:
        _enc                = None
        _CIFRADO_DISPONIBLE = False

BUFFER_SIZE = 65535
TIMEOUT     = 5.0


def crear_paquete(seq: int, ack: int, flags: str,
                  data: str = "", trace_id: str = None) -> bytes:
    """
    Construye, serializa y cifra un paquete UDP.

    Pasos:
      1. Arma el dict del paquete.
      2. Lo convierte a JSON (bytes UTF-8).
      3. Si el encriptador tiene clave activa → cifra con Fernet.
      4. Devuelve bytes listos para socket.sendto().
    """
    paquete = {
        "seq":       seq,
        "ack":       ack,
        "flags":     flags,
        "data":      data,
        "trace_id":  trace_id or str(uuid.uuid4())[:8],
        "timestamp": time.time(),
    }
    raw = json.dumps(paquete).encode("utf-8")

    if _CIFRADO_DISPONIBLE and _enc is not None:
        return _enc.encrypt(raw)    # b"ENC:..." o b"PLAIN:..."
    return raw                      # modo original sin cifrado


def desempaquetar(bytes_data: bytes) -> dict | None:
    """
    Descifra (si aplica) y deserializa un paquete UDP recibido.

    Pasos:
      1. Si el encriptador está disponible → intenta descifrar.
      2. Parsea el JSON resultante.
      3. Devuelve el dict o None si hay cualquier error.
    """
    if bytes_data is None:
        return None

    try:
        if _CIFRADO_DISPONIBLE and _enc is not None:
            raw = _enc.decrypt(bytes_data)
        else:
            raw = bytes_data
        return json.loads(raw.decode("utf-8"))

    except Exception:
        # Fallback: intentar parsear directamente (paquetes de versión anterior
        # o paquetes enviados por nodos sin cifrado activo)
        try:
            return json.loads(bytes_data.decode("utf-8"))
        except Exception:
            return None