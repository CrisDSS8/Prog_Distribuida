# -*- coding: utf-8 -*-
"""
------------------------------------------------------------
  PRACTICA MPI - Suma Paralela con Scatter y Gather
------------------------------------------------------------

Uso: mpiexec -n 10 python suma.py

Se necesitan 10 procesos:

Proceso 0: genera la lista, la distribuye con scatter y recolecta resultados con gather

Procesos 1 al 9: reciben su porcion, suman y devuelven el resultado con gather

NOTA: scatter y gather incluyen al proceso 0 como trabajador, por eso aparecen 10 sumas parciales (rank 0 al 9). 
El orden de impresion es aleatorio porque todos los procesos corren en paralelo. """

import sys
import io
import random
from mpi4py import MPI

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ---- 1. Inicializacion del entorno MPI ---------------------------------------
comm = MPI.COMM_WORLD         
rank = comm.Get_rank()         
size = comm.Get_size()         

TOTAL_NUMEROS = 1_000_000      
RANGO_MIN     = 1              
RANGO_MAX     = 1000           


# ---- 2. Proceso 0: genera la lista y prepara los chunks ----------------------
if rank == 0:
    t_inicio = MPI.Wtime()     

    print(f"[Proceso 0] Generando {TOTAL_NUMEROS:,} numeros aleatorios...")
    lista_completa = [random.randint(RANGO_MIN, RANGO_MAX)
                      for _ in range(TOTAL_NUMEROS)]

    
    if TOTAL_NUMEROS % size != 0:
        nuevo_total = (TOTAL_NUMEROS // size) * size
        lista_completa = lista_completa[:nuevo_total]
        print(f"[Proceso 0] AVISO: lista recortada a {nuevo_total:,} elementos.")

    elementos_por_proceso = len(lista_completa) // size

    chunks = [
        lista_completa[i * elementos_por_proceso : (i + 1) * elementos_por_proceso]
        for i in range(size)
    ]

    print(f"[Proceso 0] Lista dividida: {size} procesos x "
          f"{elementos_por_proceso:,} elementos cada uno.")
    print(f"[Proceso 0] Dispersando datos (scatter)...")
else:
    chunks = None


# ---- 3. Scatter: repartir porciones a todos los procesos ---------------------
mi_porcion = comm.scatter(chunks, root=0)


# ---- 4. Cada proceso suma su porcion de forma independiente ------------------
mi_suma = sum(mi_porcion)

# Este print aparecera en orden aleatorio porque todos los
# procesos lo ejecutan al mismo tiempo (paralelismo real)
print(f"  [Proceso {rank:>3}] Recibi {len(mi_porcion):,} elementos  ->  "
      f"mi suma parcial = {mi_suma:,}")


# ---- 5. Gather: reunir todas las sumas en el proceso 0 -----------------------
# gather recolecta mi_suma de cada proceso y forma una lista en rank 0.
# En los demas procesos devuelve None.
todas_las_sumas = comm.gather(mi_suma, root=0)


# ---- 6. Proceso 0: calcular y mostrar el resultado final ---------------------
if rank == 0:
    suma_total = sum(todas_las_sumas)

    t_fin = MPI.Wtime()
    tiempo_ejecucion = t_fin - t_inicio

    print()
    print("=" * 55)
    print(f"  RESULTADO FINAL")
    print("=" * 55)
    print(f"  Numero de procesos   : {size}")
    print(f"  Elementos procesados : {len(lista_completa):,}")
    print(f"  Sumas parciales      : {todas_las_sumas}")
    print(f"  SUMA TOTAL           : {suma_total:,}")
    print(f"  Tiempo de ejecucion  : {tiempo_ejecucion:.6f} segundos")
    print("=" * 55)