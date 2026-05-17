from xmlrpc.server import SimpleXMLRPCServer
from socketserver import ThreadingMixIn
import time

"""
SERVIDOR RPC CONCURRENTE

Descripción:
Este servidor implementa un servicio RPC (Remote Procedure Call, utilizando XML-RPC en Python. 
Permite a múltiples clientes realizar peticiones simultáneamente gracias al uso de hilos (ThreadingMixIn).

Operaciones disponibles:
- suma(x, y)
- resta(x, y)
- multiplica(x, y)
- factorial(x)

Puerto de escucha: 8000, Dirección: 0.0.0.0 (todas las interfaces de red)
"""

# FUNCIÓN AUXILIAR DE LOG
def log(msg):
    """
    Imprime mensajes en consola con formato del servidor.

    Parámetros:
        msg (str): Mensaje a mostrar
    """
    print(f"[SERVER] {msg}")

# FUNCIONES REMOTAS
def add(x, y):
    """
    Realiza la suma de dos números.

    Parámetros:
        x (int/float): Primer operando
        y (int/float): Segundo operando

    Retorna:
        int/float: Resultado de la suma
    """
    log(f"Petición recibida: suma({x}, {y})")
    result = x + y
    log(f"Resultado enviado: {result}")
    return result


def sub(x, y):
    """
    Realiza la resta de dos números.

    Parámetros:
        x (int/float): Minuendo
        y (int/float): Sustraendo

    Retorna:
        int/float: Resultado de la resta
    """
    log(f"Petición recibida: resta({x}, {y})")
    result = x - y
    log(f"Resultado enviado: {result}")
    return result


def mul(x, y):
    """
    Realiza la multiplicación de dos números.

    Parámetros:
        x (int/float): Primer factor
        y (int/float): Segundo factor

    Retorna:
        int/float: Resultado de la multiplicación
    """
    log(f"Petición recibida: multiplica({x}, {y})")
    result = x * y
    log(f"Resultado enviado: {result}")
    return result


def fac(x):
    """
    Calcula el factorial de un número de forma recursiva.

    Parámetros:
        x (int): Número entero no negativo

    Retorna:
        int: Factorial de x

    Nota:
        Se incluye una pequeña pausa (sleep) para simular
        carga de procesamiento y evidenciar la concurrencia.
    """
    log(f"Petición recibida: factorial({x})")

    # Simulación de carga de trabajo
    time.sleep(0.2)

    # Caso base
    if x == 0:
        result = 1
    else:
        # Llamada recursiva
        result = x * fac(x - 1)

    log(f"Resultado enviado: factorial({x}) = {result}")
    return result

# SERVIDOR CONCURRENTE
class ThreadedRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    """
    Clase que permite manejar múltiples peticiones simultáneamente
    mediante el uso de hilos (concurrencia).
    """
    pass

# INICIALIZACIÓN DEL SERVIDOR
with ThreadedRPCServer(("0.0.0.0", 8000), allow_none=True) as server:
    """
    Se crea el servidor RPC en el puerto 8000 y se registran
    las funciones que podrán ser invocadas remotamente por los clientes.
    """

    # Registro de funciones remotas
    server.register_function(add, "suma")
    server.register_function(sub, "resta")
    server.register_function(mul, "multiplica")
    server.register_function(fac, "factorial")

    print("\n[SERVER] Servidor RPC CONCURRENTE iniciado en puerto 8000\n")

    # Inicio del servicio (escucha infinita)
    server.serve_forever()