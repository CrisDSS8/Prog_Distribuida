"""
mpi_worker.py
Proceso MPI que se lanza desde aggregations.py.
El proceso raíz (rank 0) reparte datos y combina resultados.
Los workers (rank > 0) calculan su parcial y lo devuelven al raíz.

Se ejecuta con:
  mpiexec -n 4 python mpi_worker.py
Los argumentos llegan por stdin como JSON para evitar límites de argv.
"""

import sys
import json
from mpi4py import MPI


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    # ── Rank 0: recibe args por stdin, reparte chunks ─────────────────────────
    if rank == 0:
        raw  = sys.stdin.read()
        args = json.loads(raw)
        op   = args["op"]       # "sum" | "avg" | "count"
        data = args["data"]     # lista de valores numéricos ya extraídos de MySQL

        # dividir datos en chunks iguales para cada worker
        chunks = _split(data, size)
    else:
        op     = None
        chunks = None

    # broadcast de la operación a todos los workers
    op = comm.bcast(op, root=0)

    # scatter: cada proceso recibe su chunk
    chunk = comm.scatter(chunks, root=0)

    # ── Cada worker calcula su parcial ────────────────────────────────────────
    partial = _compute_partial(op, chunk)

    # ── Gather: el raíz recolecta todos los parciales ─────────────────────────
    all_partials = comm.gather(partial, root=0)

    # ── Rank 0: combina y devuelve resultado por stdout ───────────────────────
    if rank == 0:
        result = _combine(op, all_partials, len(data))
        print(json.dumps({"value": result}))


def _split(data: list, n: int) -> list:
    """Divide la lista en n chunks lo más iguales posible."""
    size   = len(data)
    chunk  = max(1, size // n)
    chunks = []
    for i in range(n):
        start = i * chunk
        end   = start + chunk if i < n - 1 else size
        chunks.append(data[start:end])
    return chunks


def _compute_partial(op: str, chunk: list) -> dict:
    """Calcula el valor parcial para el chunk recibido."""
    if not chunk:
        return {"sum": 0, "count": 0}

    numeric = [v for v in chunk if v is not None]

    return {
        "sum":   sum(numeric),
        "count": len(numeric),
        "min":   min(numeric) if numeric else None,
        "max":   max(numeric) if numeric else None,
    }


def _combine(op: str, partials: list, total_rows: int) -> float:
    """Combina los resultados parciales de todos los workers."""
    total_sum   = sum(p["sum"]   for p in partials)
    total_count = sum(p["count"] for p in partials)

    if op == "sum":
        return total_sum

    if op == "count":
        return float(total_count)

    if op == "avg":
        return total_sum / total_count if total_count > 0 else 0.0

    return 0.0


if __name__ == "__main__":
    main()
