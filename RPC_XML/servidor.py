"""
servidor.py — Servidor XML-RPC concurrente para gestión de productos en un archivo XML.
"""

from xmlrpc.server import SimpleXMLRPCServer
from socketserver import ThreadingMixIn
import threading
import time
import xml.etree.ElementTree as ET
from queue import PriorityQueue
from itertools import count


class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    """Servidor XML-RPC que atiende cada cliente en un hilo independiente."""
    pass


archivo_xml = "productos.xml"
lock = threading.Lock()
cola = PriorityQueue()
contador = count()


def inicializar_xml():
    """
    Crea el archivo XML con raíz <productos> si no existe.

    Returns:
        None
    """
    try:
        ET.parse(archivo_xml)
    except FileNotFoundError:
        tree = ET.ElementTree(ET.Element("productos"))
        tree.write(archivo_xml)


def insertar_producto(id, nombre, precio):
    """
    Encola una inserción con prioridad alta (0) y espera el resultado.

    Args:
        id (int): Identificador único del producto.
        nombre (str): Nombre del producto.
        precio (float): Precio del producto.

    Returns:
        int: Posición del producto insertado, o -1 si el ID ya existe.
    """
    evento = threading.Event()
    resultado = {}
    cola.put((0, next(contador), ("insertar", id, nombre, precio, evento, resultado)))
    evento.wait()
    return resultado["pos"]


def consultar_producto(id):
    """
    Encola una consulta con prioridad normal (1) y espera el resultado.

    Args:
        id (int): Identificador del producto a buscar.

    Returns:
        int: Posición del producto en el XML, o -1 si no existe.
    """
    evento = threading.Event()
    resultado = {}
    cola.put((1, next(contador), ("consultar", id, None, None, evento, resultado)))
    evento.wait()
    return resultado["pos"]


def worker():
    """
    Procesa tareas de la cola en orden de prioridad de forma serial.

    Lee o escribe el archivo XML bajo un Lock para evitar condiciones
    de carrera. Un solo worker garantiza que la prioridad se respete
    en el orden de finalización.

    Returns:
        None
    """
    while True:
        prioridad, orden, tarea = cola.get()
        tipo, id, nombre, precio, evento, resultado = tarea

        print(f"Procesando {tipo} (ID={id})...")

        with lock:
            tree = ET.parse(archivo_xml)
            root = tree.getroot()

            if tipo == "insertar":
                time.sleep(3)
                existe = any(p.find("id").text == str(id) for p in root.findall("producto"))
                if existe:
                    resultado["pos"] = -1
                    print(f"ID={id} ya existe.")
                else:
                    nuevo = ET.Element("producto")
                    ET.SubElement(nuevo, "id").text = str(id)
                    ET.SubElement(nuevo, "nombre").text = nombre
                    ET.SubElement(nuevo, "precio").text = str(precio)
                    root.append(nuevo)
                    ET.indent(tree, space="  ")
                    tree.write(archivo_xml, encoding="utf-8", xml_declaration=True)
                    resultado["pos"] = len(root) - 1
                    print(f"Insertado ID={id} en posición {resultado['pos']}.")

            elif tipo == "consultar":
                resultado["pos"] = next(
                    (i for i, p in enumerate(root.findall("producto")) if p.find("id").text == str(id)),
                    -1
                )
                print(f"Consulta ID={id} → posición {resultado['pos']}.")

        evento.set()
        cola.task_done()


if __name__ == "__main__":
    inicializar_xml()

    # Un único worker respeta estrictamente el orden de prioridad
    threading.Thread(target=worker, daemon=True).start()

    server = ThreadedXMLRPCServer(("0.0.0.0", 8000), allow_none=True)
    server.register_function(insertar_producto, "insertar")
    server.register_function(consultar_producto, "consultar")

    print("Servidor ejecutándose en puerto 8000...")
    server.serve_forever()
