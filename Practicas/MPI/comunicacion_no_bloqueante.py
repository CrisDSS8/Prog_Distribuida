from mpi4py import MPI
import time

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

TAG_DATA = 10
TAG_RESP = 20

t0 = time.time()

def ts():
    return f"{time.time() - t0:6.2f}s"

if rank == 0:
    dato1 = 100
    dato2 = 200

    print(f"[{ts()}] Proceso 0: iniciando envíos no bloqueantes")

    req_s1 = comm.isend(dato1, dest=1, tag=TAG_DATA)
    req_s2 = comm.isend(dato2, dest=2, tag=TAG_DATA)

    print(f"[{ts()}] Proceso 0: publicando recepciones no bloqueantes")

    req_r1 = comm.irecv(source=1, tag=TAG_RESP)
    req_r2 = comm.irecv(source=2, tag=TAG_RESP)

    print(f"[{ts()}] Proceso 0: simulando cómputo útil por 3 segundos")
    time.sleep(3)

    print(f"[{ts()}] Proceso 0: terminó cómputo útil")
    print(f"[{ts()}] Proceso 0: esperando que terminen los envíos")

    MPI.Request.Waitall([req_s1, req_s2])

    print(f"[{ts()}] Proceso 0: envíos completados")
    print(f"[{ts()}] Proceso 0: esperando respuesta del proceso 1")
    resp1 = req_r1.wait()

    print(f"[{ts()}] Proceso 0: respuesta de 1 recibida: {resp1}")
    print(f"[{ts()}] Proceso 0: esperando respuesta del proceso 2")
    resp2 = req_r2.wait()

    print(f"[{ts()}] Proceso 0: respuesta de 2 recibida: {resp2}")
    print(f"[{ts()}] Proceso 0: ya puede continuar")

elif rank == 1:
    print(f"[{ts()}] Proceso 1: esperando dato")
    x = comm.recv(source=0, tag=TAG_DATA)

    print(f"[{ts()}] Proceso 1: recibió {x}, procesando 2 segundos")
    time.sleep(2)

    resultado = x * 10
    comm.send(resultado, dest=0, tag=TAG_RESP)
    print(f"[{ts()}] Proceso 1: envió respuesta {resultado}")

elif rank == 2:
    print(f"[{ts()}] Proceso 2: esperando dato")
    x = comm.recv(source=0, tag=TAG_DATA)

    print(f"[{ts()}] Proceso 2: recibió {x}, procesando 4 segundos")
    time.sleep(4)

    resultado = x * 10
    comm.send(resultado, dest=0, tag=TAG_RESP)
    print(f"[{ts()}] Proceso 2: envió respuesta {resultado}")