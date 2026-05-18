"""
cliente.py — Cliente gRPC con soporte para peticiones paralelas.

Uso interactivo:
    python3 cliente.py

Uso directo:
    python3 cliente.py --expr "5+3*2-1" --host localhost --port 50160

Prueba de concurrencia (varias expresiones simultáneas):
    python3 cliente.py --paralelo --host localhost --port 50160
"""

import argparse
import uuid
import threading
import grpc
from protos import calculadora_pb2, calculadora_pb2_grpc


def calcular(stub, expr: str) -> str:
    """Envía la expresión con un ID único y devuelve el resultado."""
    id_peticion = str(uuid.uuid4())[:8]  # ID corto legible
    try:
        respuesta = stub.Calcular(
            calculadora_pb2.Expresion(expr=expr, id=id_peticion)
        )
        campo = respuesta.WhichOneof("resultado")
        id_resp = respuesta.id or id_peticion
        if campo == "data":
            return f"[{id_resp}]  {expr} = {respuesta.data}"
        else:
            return f"[{id_resp}]  Error: {respuesta.error}"
    except grpc.RpcError as e:
        return f"[{id_peticion}]  Error gRPC: {e.details()}"


def modo_interactivo(stub):
    """Bucle interactivo para ingresar expresiones desde la terminal."""
    print("   Calculadora distribuida gRPC           ")
    print("   Escribe una expresión matemática       ")
    print("   Ejemplo: 5+3*2-1  |  10/2+4            ")
    print("   'paralelo' → prueba de concurrencia    ")
    print("   'salir'    → terminar                  ")

    while True:
        try:
            expr = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not expr:
            continue
        if expr.lower() in ("salir", "exit", "q"):
            print("Hasta luego.")
            break
        if expr.lower() == "paralelo":
            modo_paralelo(stub)
            continue

        print("   ", calcular(stub, expr))


def modo_paralelo(stub):
    """
    Lanza varias peticiones simultáneas para demostrar concurrencia.
    Cada petición tiene su propio ID — los resultados llegan en
    cualquier orden pero cada uno identifica a qué petición pertenece.
    """
    expresiones = [
        "5+3*2-1",
        "10/2+4",
        "2*3+4*5",
        "100/4-5",
        "7*7-7",
        "50/5+3*2",
    ]

    print(f"\n  Lanzando {len(expresiones)} peticiones en paralelo...\n")
    resultados = {}
    lock = threading.Lock()

    def enviar(expr):
        resultado = calcular(stub, expr)
        with lock:
            resultados[expr] = resultado
            print("   ", resultado)

    hilos = [threading.Thread(target=enviar, args=(e,)) for e in expresiones]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    print(f"\n  {len(resultados)}/{len(expresiones)} peticiones completadas.\n")


def main():
    parser = argparse.ArgumentParser(description="Cliente de la calculadora distribuida")
    parser.add_argument("--host",     type=str, default="172.31.7.137")
    parser.add_argument("--port",     type=int, default=8000)
    parser.add_argument("--expr",     type=str, default=None,
                        help="Expresión a calcular (modo directo)")
    parser.add_argument("--paralelo", action="store_true",
                        help="Prueba de concurrencia con varias expresiones")
    args = parser.parse_args()

    canal = grpc.insecure_channel(f"{args.host}:{args.port}")
    stub  = calculadora_pb2_grpc.OrquestadorServiceStub(canal)

    if args.paralelo:
        modo_paralelo(stub)
    elif args.expr:
        print(calcular(stub, args.expr))
    else:
        modo_interactivo(stub)


if __name__ == "__main__":
    main()
