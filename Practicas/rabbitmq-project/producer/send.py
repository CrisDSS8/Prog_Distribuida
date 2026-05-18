import pika
import time

time.sleep(15)  

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq')
)
channel = connection.channel()
channel.queue_declare(queue='hello')

channel.basic_publish(
    exchange='',
    routing_key='hello',
    body='Hello World desde Python!'
)
print(" [x] Enviado: 'Hello World desde Python!'")
connection.close()