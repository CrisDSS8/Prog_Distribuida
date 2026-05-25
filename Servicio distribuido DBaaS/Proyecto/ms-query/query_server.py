"""
query_server.py
Punto de entrada del MS6 — Query / Aggregation Service.
Recibe IROperation del broker y delega en aggregations.py o join_executor.py.
"""

import grpc
import json
import os
import sys
from concurrent import futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../protos"))
import dbaas_pb2
import dbaas_pb2_grpc

import aggregations
import join_executor

PORT = os.getenv("QUERY_PORT", "50055")


class QueryServicer(dbaas_pb2_grpc.QueryServiceServicer):

    def Count(self, request, context):
        ir     = _to_ir(request)
        result = aggregations.count(ir)
        return dbaas_pb2.ScalarResponse(
            success = result["success"],
            message = result.get("message", ""),
            value   = result.get("value", 0.0),
        )

    def Sum(self, request, context):
        ir     = _to_ir(request)
        result = aggregations.sum_field(ir)
        return dbaas_pb2.ScalarResponse(
            success = result["success"],
            message = result.get("message", ""),
            value   = result.get("value", 0.0),
        )

    def Avg(self, request, context):
        ir     = _to_ir(request)
        result = aggregations.avg_field(ir)
        return dbaas_pb2.ScalarResponse(
            success = result["success"],
            message = result.get("message", ""),
            value   = result.get("value", 0.0),
        )

    def Distinct(self, request, context):
        ir     = _to_ir(request)
        result = aggregations.distinct(ir)
        return dbaas_pb2.DistinctResponse(
            success = result["success"],
            message = result.get("message", ""),
            values  = result.get("values", []),
        )

    def Join(self, request, context):
        ir     = _to_ir(request)
        result = join_executor.execute_join(ir)
        docs   = [json.dumps(d, default=str) for d in result.get("documents", [])]
        return dbaas_pb2.JoinResponse(
            success   = result["success"],
            message   = result.get("message", ""),
            documents = docs,
        )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_ir(request) -> dict:
    """Convierte el IROperation proto a dict Python."""
    return {
        "operation": request.operation,
        "database":  request.database,
        "table":     request.table,
        "fields":    request.fields  or '["*"]',
        "filter":    request.filter  or "{}",
        "options":   request.options or "{}",
        "role":      request.role,
        "user_id":   request.user_id,
    }


# ── Servidor ──────────────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dbaas_pb2_grpc.add_QueryServiceServicer_to_server(QueryServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print(f"[query] escuchando en puerto {PORT}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
