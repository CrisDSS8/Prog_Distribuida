from xmlrpc.server import SimpleXMLRPCServer
from queue import Queue
import threading

cola_vectores = Queue()
cola_resultados = Queue()

MAX_RESULTADOS = 1000000
contador = 0
lock = threading.Lock()

def almacenar_vector(vector):
    cola_vectores.put(vector)
    print("Vector almacenado:", vector)
    return True


def obtener_vector():
    if not cola_vectores.empty():
        vector = cola_vectores.get()
        return vector
    else:
        return []


def guardar_resultado(resultado):
    global contador
    
    cola_resultados.put(resultado)

    with lock:
        contador += 1
        print("Resultado recibido:", resultado)

        if contador >= MAX_RESULTADOS:
            total = 0

            while not cola_resultados.empty():
                total += cola_resultados.get()

            print("\nRESULTADOS COMPLETOS")
            print("Suma total:", total)

    return True


server = SimpleXMLRPCServer(("0.0.0.0", 8000))
print("Servidor RPC iniciado en puerto 8000")

server.register_function(almacenar_vector, "almacenar_vector")
server.register_function(obtener_vector, "obtener_vector")
server.register_function(guardar_resultado, "guardar_resultado")

server.serve_forever()