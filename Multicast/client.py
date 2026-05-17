import socket
import json
import time
import sys
import random

SERVER_HOST = '127.0.0.1'
CLIENT_PORT = 5009
BUFFER_SIZE = 4096
TIMEOUT     = 10.0


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


def gcd_vector(nums):
    """
    Calcula el Máximo Común Divisor de una lista de números.
    Se usa localmente para verificar que el resultado del servidor sea correcto.

    Parámetros:
        nums (list[int]): Lista de números enteros.

    Retorna:
        int: El MCD de todos los números en la lista.
    """
    r = abs(nums[0])
    for n in nums[1:]:
        r = gcd2(r, abs(n))
    return r


def generar_vector():
    """
    Genera un vector de 5 números enteros aleatorios entre 1 y 500.

    Parámetros:
        None

    Retorna:
        list[int]: Lista de 5 enteros aleatorios.
    """
    return [random.randint(1, 500) for _ in range(5)]


def enviar_peticion(numbers, numero):
    """
    Envía un vector al servidor vía UDP y espera la respuesta con el MCD calculado.
    Compara el resultado recibido con el MCD calculado localmente para verificar
    que la respuesta del servidor sea correcta.

    Parámetros:
        numbers (list[int]): Vector de 5 números a enviar al servidor.
        numero  (int):       Número de ejecución actual (para mostrar en pantalla).

    Retorna:
        float | None: Tiempo de respuesta en milisegundos si fue exitosa,
                      None si ocurrió un timeout.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    try:
        t0 = time.time()
        sock.sendto(json.dumps({'numbers': numbers}).encode(), (SERVER_HOST, CLIENT_PORT))
        data, _ = sock.recvfrom(BUFFER_SIZE)
        elapsed = (time.time() - t0) * 1000
        resp = json.loads(data.decode())

        mcd_real = gcd_vector(numbers)

        if resp.get('status') == 'ok':
            correcto = "OK" if resp['result'] == mcd_real else "ERROR"
            print(f"  [{numero:>3}] {correcto} Vector: {numbers}")
            print(f"        MCD={resp['result']} | "
                  f"Politica={resp.get('policy')} | "
                  f"Replicas={resp.get('responses_received')} | "
                  f"Tiempo={elapsed:.1f}ms")
        else:
            print(f"  [{numero:>3}] Error: {resp.get('status')} -> {numbers}")

        return elapsed

    except socket.timeout:
        print(f"  [{numero:>3}] Timeout para {numbers}")
        return None
    finally:
        sock.close()


if __name__ == '__main__':
    total     = int(sys.argv[1])   if len(sys.argv) > 1 else 10
    intervalo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3

    print("=" * 55)
    print(f"  Cliente automatico MCD")
    print(f"  Peticiones : {total}")
    print(f"  Intervalo  : {intervalo}s entre cada una")
    print("=" * 55)
    print()

    tiempos  = []
    exitosas = 0

    for i in range(1, total + 1):
        vector = generar_vector()
        t = enviar_peticion(vector, i)
        if t is not None:
            tiempos.append(t)
            exitosas += 1
        time.sleep(intervalo)

    print()
    print("-" * 55)
    print(f"  Resumen:")
    print(f"  Peticiones enviadas  : {total}")
    print(f"  Respuestas exitosas  : {exitosas}")
    if tiempos:
        print(f"  Tiempo minimo        : {min(tiempos):.1f} ms")
        print(f"  Tiempo maximo        : {max(tiempos):.1f} ms")
        print(f"  Tiempo promedio      : {sum(tiempos)/len(tiempos):.1f} ms")
    print("-" * 55)