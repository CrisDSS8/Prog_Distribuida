import xmlrpc.client
import time
import threading
import random

"""
CLIENTE RPC CONCURRENTE

Descripción:
Este programa actúa como cliente de un servidor RPC utilizando XML-RPC.
Su objetivo es enviar múltiples peticiones concurrentes al servidor
para evaluar su rendimiento y capacidad de manejo de concurrencia.

Cada petición solicita el cálculo del factorial de un número aleatorio
entre 1 y 12.

Características:
- Generación de múltiples hilos (threads)
- Envío concurrente de peticiones
- Medición de tiempos de ejecución
- Conteo de peticiones exitosas y fallidas
"""

# CONFIGURACIÓN
peticiones = 100000  
exitos = 0           
lock = threading.Lock()  

def log(msg):
    """
    Imprime mensajes en consola con formato del cliente.

    Parámetros:
        msg (str): Mensaje a mostrar
    """
    print(f"[CLIENTE] {msg}")

# FUNCIÓN QUE ENVÍA PETICIONES
def hacer_peticion(i):
    """
    Realiza una petición al servidor RPC solicitando el cálculo
    del factorial de un número aleatorio.

    Parámetros:
        i (int): Identificador de la petición

    Comportamiento:
        - Genera un número aleatorio entre 1 y 12
        - Envía la petición al servidor
        - Recibe y muestra el resultado
        - Incrementa el contador de éxitos
    """
    global exitos

    try:
        proxy = xmlrpc.client.ServerProxy("http://172.31.5.166:8000")

        valor = random.randint(1, 12)

        log(f"Enviando petición #{i}: factorial({valor})")
        
        resultado = proxy.factorial(valor)

        log(f"Respuesta recibida #{i}: factorial({valor}) = {resultado}")
        
        with lock:
            exitos += 1
        
        if i % 100 == 0:
            print(f"[CLIENTE] {i} peticiones completadas")

    except Exception as e:
        log(f"Error en petición #{i}: {e}")

# EJECUCIÓN CONCURRENTE
threads = []  
start = time.time() 

"""
Se crean múltiples hilos, cada uno ejecutando una petición
independiente al servidor.
"""
for i in range(peticiones):
    t = threading.Thread(target=hacer_peticion, args=(i,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()

end = time.time() 

# RESULTADOS
"""
Se muestran estadísticas finales del experimento:
- Total de peticiones realizadas
- Número de peticiones exitosas
- Número de peticiones fallidas
- Tiempo total de ejecución
- Tiempo promedio por petición
"""

print("\n===== RESULTADOS =====")
print("Total peticiones:", peticiones)
print("Exitosas:", exitos)
print("Fallidas:", peticiones - exitos)
print("Tiempo total:", round(end - start, 2), "segundos")
print("Tiempo promedio:", round((end - start) / peticiones * 1000, 2), "ms por petición")