"""
cliente.py — Cliente XML-RPC que simula operaciones aleatorias de inserción y consulta.
"""

import xmlrpc.client
import threading
import random
import time


def cliente(id_cliente):
    """
    Ejecuta 15 operaciones aleatorias (insertar/consultar) contra el servidor.

    Args:
        id_cliente (int): Identificador del cliente, usado para distinguir
            la salida en consola cuando varios hilos corren en paralelo.

    Returns:
        None
    """
    # Cada hilo necesita su propio ServerProxy para evitar condiciones de carrera
    server = xmlrpc.client.ServerProxy("http://localhost:8000/", allow_none=True)

    for i in range(15):
        operacion = random.choice(["insertar", "consultar"])

        if operacion == "insertar":
            id_prod = random.randint(1, 100)
            nombre = f"Producto_{id_prod}"
            precio = random.randint(10, 100)
            print(f"[CLIENTE {id_cliente}] Insertando ID={id_prod}...")
            pos = server.insertar(id_prod, nombre, precio)
            print(f"[CLIENTE {id_cliente}] Insertado en posición {pos}.")
        else:
            id_prod = random.randint(1, 10)
            print(f"[CLIENTE {id_cliente}] Consultando ID={id_prod}...")
            pos = server.consultar(id_prod)
            print(f"[CLIENTE {id_cliente}] Resultado posición {pos}.")

        time.sleep(random.uniform(0.5, 2))


def main():
    """
    Lanza 2 clientes concurrentes y espera a que todos finalicen.

    Returns:
        None
    """
    hilos = [threading.Thread(target=cliente, args=(i,)) for i in range(2)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()
    print("Todas las operaciones finalizaron.")


if __name__ == "__main__":
    main()
