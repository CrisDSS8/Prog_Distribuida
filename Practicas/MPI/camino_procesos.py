from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.rank
print("my rank is: ", rank)

if rank == 0:
    dato_enviadoP1 = int(input("Ingresa un numero: "))
    destination_process = 1
    comm.send(dato_enviadoP1, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP1 + \
        "al proceso %d" % destination_process)
    
    dato_final = comm.recv(source=7)
    print("Dato final recibido:", dato_final)

if rank == 1:
    dato_recibidoP0 = comm.recv(source=0)
    dato_enviadoP2 = dato_recibidoP0 * 2
    destination_process = 2
    comm.send(dato_enviadoP2, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP2 + \
          "al proceso %d" % destination_process)
    
if rank == 2:
    dato_recibidoP1 = comm.recv(source=1)
    dato_enviadoP3 = dato_recibidoP1 + 10
    destination_process = 3
    comm.send(dato_enviadoP3, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP3 + \
          "al proceso %d" % destination_process)

if rank == 3:
    dato_recibidoP2 = comm.recv(source=2)
    dato_enviadoP4 = dato_recibidoP2 / 5
    destination_process = 4
    comm.send(dato_enviadoP4, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP4 + \
          "al proceso %d" % destination_process)

if rank == 4:
    dato_recibidoP3 = comm.recv(source=3)
    dato_enviadoP5 = dato_recibidoP3 * 2
    destination_process = 5
    comm.send(dato_enviadoP5, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP5 + \
          "al proceso %d" % destination_process)

if rank == 5:
    dato_recibidoP4 = comm.recv(source=4)
    dato_enviadoP6 = dato_recibidoP4 - 6 
    destination_process = 6
    comm.send(dato_enviadoP6, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP6 + \
          "al proceso %d" % destination_process)

if rank == 6:
    dato_recibidoP5 = comm.recv(source=5)
    dato_enviadoP7 = dato_recibidoP5 / 3
    destination_process = 7
    comm.send(dato_enviadoP7, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP7 + \
          "al proceso %d" % destination_process)
    
if rank == 7:
    dato_recibidoP6 = comm.recv(source=6)
    dato_enviadoP0 = dato_recibidoP6 + 5
    destination_process = 0
    comm.send(dato_enviadoP0, dest=destination_process)
    print("Enviando dato %s " % dato_enviadoP0 + \
          "al proceso %d" % destination_process)
    


