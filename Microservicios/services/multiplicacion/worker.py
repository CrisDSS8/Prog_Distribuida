#!/usr/bin/env python3
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'proto'))

import pika, grpc
import calculadora_pb2
import calculadora_pb2_grpc

RABBITMQ_HOST  = os.environ.get("RABBITMQ_HOST",  "localhost")
GRPC_MULT_HOST = os.environ.get("GRPC_MULT_HOST", "localhost")
GRPC_MULT_PORT = os.environ.get("GRPC_MULT_PORT", "50053")
QUEUE          = "multiplicacion"

def get_stub():
    ch = grpc.insecure_channel(f"{GRPC_MULT_HOST}:{GRPC_MULT_PORT}")
    return calculadora_pb2_grpc.MultiplicacionStub(ch)

def callback(ch, method, properties, body):
    msg = json.loads(body)
    print(f"[WORKER-MULT] {msg['num1']} × {msg['num2']}")
    try:
        resp = get_stub().Calcular(
            calculadora_pb2.Numeros(num1=msg["num1"], num2=msg["num2"]))
        result = {"data": resp.data, "error": None} if resp.HasField("data") \
                 else {"data": None, "error": resp.error}
    except Exception as e:
        result = {"data": None, "error": str(e)}

    if properties.reply_to:
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(result),
        )
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(f"[WORKER-MULT] → {result}")

def main():
    while True:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            ch   = conn.channel()
            ch.queue_declare(queue=QUEUE, durable=True)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=QUEUE, on_message_callback=callback)
            print(f"[WORKER-MULT] Esperando en cola '{QUEUE}' …")
            ch.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("[WORKER-MULT] Sin conexión, reintentando …")
            time.sleep(5)

if __name__ == "__main__":
    main()