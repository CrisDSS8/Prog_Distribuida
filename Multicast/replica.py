import socket
import struct
import json
import time
import sys
import random

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT  = 5007
BUFFER_SIZE     = 4096


def gcd2(a, b):
    """
    Calcula el Máximo Común Divisor de dos números usando el algoritmo de Euclides.

    Parámetros:
        a (int): Primer número entero.
        b (int): Segundo número entero.

    Retorna:
        int: El MCD de a y b.
    """
    while b:
        a, b = b, a % b
    return a


def gcd_vector(numbers):
    """
    Calcula el Máximo Común Divisor de una lista de números.
    Aplica gcd2 de forma acumulativa sobre todos los elementos del vector.

    Parámetros:
        numbers (list[int]): Lista de números enteros.

    Retorna:
        int: El MCD de todos los números en la lista.
    """
    result = abs(numbers[0])
    for n in numbers[1:]:
        result = gcd2(result, abs(n))
    return result


def run_replica(replica_id, delay_ms=0):
    """
    Inicia una réplica que escucha tareas por multicast UDP, calcula el MCD
    del vector recibido y envía el resultado de vuelta al servidor vía UDP unicast.

    La réplica se une al grupo multicast definido en MULTICAST_GROUP y permanece
    en espera indefinida de tareas. Por cada tarea recibida aplica un retardo
    simulado antes de calcular para emular latencia de red real.

    Parámetros:
        replica_id (int): Identificador único de esta réplica (ej. 1, 2, 3).
        delay_ms   (int): Retardo artificial en milisegundos antes de calcular.
                          Por defecto es 0 (sin retardo).

    Retorna:
        None: Esta función corre en bucle infinito hasta ser interrumpida.
    """
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(('', MULTICAST_PORT))

    mreq = struct.pack('4sL', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    recv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[Replica {replica_id}] Escuchando en {MULTICAST_GROUP}:{MULTICAST_PORT}")

    while True:
        try:
            data, _ = recv_sock.recvfrom(BUFFER_SIZE)
            msg = json.loads(data.decode())

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0 + random.uniform(0, 0.01))

            result = gcd_vector(msg['numbers'])

            response = {
                'request_id': msg['request_id'],
                'replica_id': replica_id,
                'result':     result
            }

            send_sock.sendto(
                json.dumps(response).encode(),
                (msg['server_host'], msg['server_port'])
            )
            print(f"[Replica {replica_id}] MCD={result}")

        except Exception as e:
            print(f"[Replica {replica_id}] Error: {e}")


if __name__ == '__main__':
    rid = int(sys.argv[1])
    dms = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    run_replica(rid, dms)