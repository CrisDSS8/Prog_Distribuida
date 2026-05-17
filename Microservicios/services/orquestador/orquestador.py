#!/usr/bin/env python3
"""
Orquestador HTTP
  GET /calcular?expr=5+3*2-1
Variables: RABBITMQ_HOST, PORT
"""
import os, sys, json, uuid, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import pika

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
PORT          = int(os.environ.get("PORT", "8000"))

PRECEDENCIA    = {'+': 1, '-': 1, '*': 2, '/': 2}
OPERACION_COLA = {'+': 'suma', '-': 'resta', '*': 'multiplicacion', '/': 'division'}

# ── Parser Shunting-Yard ─────────────────────────────────────────

def tokenizar(expr):
    tokens, buf = [], []
    for ch in expr.replace(" ", ""):
        if ch in PRECEDENCIA or ch in "()":
            if buf: tokens.append("".join(buf)); buf = []
            tokens.append(ch)
        else:
            buf.append(ch)
    if buf: tokens.append("".join(buf))
    return tokens

def shunting_yard(tokens):
    salida, pila = [], []
    for tok in tokens:
        if tok not in PRECEDENCIA and tok not in "()":
            salida.append(float(tok))
        elif tok in PRECEDENCIA:
            while pila and pila[-1] in PRECEDENCIA and \
                  PRECEDENCIA[pila[-1]] >= PRECEDENCIA[tok]:
                salida.append(pila.pop())
            pila.append(tok)
        elif tok == "(":
            pila.append(tok)
        elif tok == ")":
            while pila and pila[-1] != "(": salida.append(pila.pop())
            pila.pop()
    while pila: salida.append(pila.pop())
    return salida

def rpn_a_operaciones(rpn):
    pila, ops = [], []
    for tok in rpn:
        if isinstance(tok, float):
            pila.append(("val", tok))
        else:
            b = pila.pop(); a = pila.pop()
            ops.append({"op": tok, "a": a, "b": b})
            pila.append(("ref", len(ops) - 1))
    return ops

# ── Cliente RabbitMQ RPC ─────────────────────────────────────────

class RpcClient:
    def __init__(self):
        self.conn    = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST))
        self.channel = self.conn.channel()
        result       = self.channel.queue_declare(queue="", exclusive=True)
        self.reply_queue = result.method.queue
        self.responses   = {}
        self._lock       = threading.Lock()
        self.channel.basic_consume(
            queue=self.reply_queue,
            on_message_callback=self._on_response,
            auto_ack=True)

    def _on_response(self, ch, method, props, body):
        with self._lock:
            self.responses[props.correlation_id] = json.loads(body)

    def call(self, cola, num1, num2, timeout=10):
        corr_id = str(uuid.uuid4())
        self.channel.queue_declare(queue=cola, durable=True)
        self.channel.basic_publish(
            exchange="",
            routing_key=cola,
            properties=pika.BasicProperties(
                reply_to=self.reply_queue,
                correlation_id=corr_id,
                delivery_mode=2),
            body=json.dumps({"num1": num1, "num2": num2}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.conn.process_data_events(time_limit=0.1)
            with self._lock:
                if corr_id in self.responses:
                    return self.responses.pop(corr_id)
        return {"data": None, "error": "Timeout"}

    def close(self): self.conn.close()

# ── Orquestación ─────────────────────────────────────────────────

def resolver(expr):
    tokens  = tokenizar(expr)
    rpn     = shunting_yard(tokens)
    ops     = rpn_a_operaciones(rpn)
    client  = RpcClient()
    results = []
    pasos   = []

    def val(v):
        kind, data = v
        return data if kind == "val" else results[data]

    try:
        for op_info in ops:
            cola = OPERACION_COLA[op_info["op"]]
            num1, num2 = val(op_info["a"]), val(op_info["b"])
            print(f"[ORQUESTADOR] → cola '{cola}': {num1} {op_info['op']} {num2}")
            resp = client.call(cola, num1, num2)
            if resp.get("error"):
                return {"resultado": None, "error": resp["error"], "pasos": pasos}
            results.append(resp["data"])
            pasos.append({"operacion": cola, "num1": num1,
                          "num2": num2, "resultado": resp["data"]})
            print(f"[ORQUESTADOR] ← {resp['data']}")
    finally:
        client.close()

    return {"resultado": results[-1] if results else None, "pasos": pasos}

# ── Servidor HTTP ─────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print(f"[HTTP] {fmt % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/calcular":
            return self._respond(404, {"error": "Ruta no encontrada"})
        params = parse_qs(parsed.query)
        expr   = params.get("expr", [None])[0]
        if not expr:
            return self._respond(400, {"error": "Parámetro 'expr' requerido"})
        print(f"[ORQUESTADOR] Expresión: {expr}")
        try:
            self._respond(200, resolver(expr))
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def main():
    print(f"[ORQUESTADOR] HTTP en :{PORT}  RabbitMQ → {RABBITMQ_HOST}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()