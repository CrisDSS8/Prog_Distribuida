"""
audit_consumer.py
Punto de entrada del ms-audit.
Consume la cola 'dbaas.audit' de RabbitMQ y guarda cada evento
en un archivo de log y en una tabla MySQL de auditoría.

El Gateway publica en esta cola después de cada operación Execute.
Este proceso corre de forma completamente independiente:
si se cae, los eventos se acumulan en RabbitMQ y se procesan
cuando vuelva a levantarse (cola durable).
"""

import json
import logging
import mysql.connector
import os
import pika
import time

# ── Logging a archivo y consola ───────────────────────────────────────────────
LOG_FILE = os.getenv("AUDIT_LOG_FILE", "audit.log")
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [audit] %(message)s",
    handlers= [
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("audit")

# ── Config ────────────────────────────────────────────────────────────────────
RABBIT_HOST  = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_PORT  = int(os.getenv("RABBITMQ_PORT", "5673"))
RABBIT_USER  = os.getenv("RABBITMQ_USER", "admin")
RABBIT_PASS  = os.getenv("RABBITMQ_PASS", "admin1234")
QUEUE_NAME   = "dbaas.audit"


# ── MySQL ─────────────────────────────────────────────────────────────────────

def _conn():
    return mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", "dbaas1234"),
        database = "dbaas_auth",          # misma DB del auth, tabla separada
    )


def init_audit_table():
    """Crea la tabla de auditoría si no existe."""
    try:
        con = _conn()
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                user_id    VARCHAR(36),
                role       VARCHAR(20),
                operation  VARCHAR(50),
                interface  VARCHAR(10),
                success    BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()
        log.info("tabla audit_log lista")
    except Exception as e:
        log.error(f"no se pudo crear audit_log: {e}")
    finally:
        cur.close(); con.close()


def save_event(event: dict):
    """Guarda el evento en MySQL."""
    try:
        con = _conn()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO audit_log (user_id, role, operation, interface, success)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            event.get("user_id",   ""),
            event.get("role",      ""),
            event.get("operation", ""),
            event.get("interface", ""),
            event.get("success",   False),
        ))
        con.commit()
    except Exception as e:
        log.error(f"error al guardar evento en MySQL: {e}")
    finally:
        cur.close(); con.close()


# ── Callback RabbitMQ ─────────────────────────────────────────────────────────

def on_message(channel, method, properties, body):
    """
    Se llama cada vez que llega un mensaje a la cola.
    1. Decodifica el JSON
    2. Loguea en archivo
    3. Guarda en MySQL
    4. Confirma el mensaje (ack) para que RabbitMQ lo elimine de la cola
    """
    try:
        event = json.loads(body)
        log.info(
            f"op={event.get('operation')} | "
            f"user={event.get('user_id')} | "
            f"role={event.get('role')} | "
            f"interface={event.get('interface')} | "
            f"success={event.get('success')}"
        )
        save_event(event)
        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        log.error(f"error procesando mensaje: {e}")
        # nack sin requeue para no entrar en loop infinito con mensajes corruptos
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# ── Conexión RabbitMQ con reintentos ──────────────────────────────────────────

def connect_rabbitmq():
    """
    Intenta conectar a RabbitMQ con reintentos.
    Útil cuando el consumidor arranca antes que RabbitMQ esté listo.
    """
    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    params      = pika.ConnectionParameters(
        host        = RABBIT_HOST,
        port        = RABBIT_PORT,
        credentials = credentials,
    )
    while True:
        try:
            connection = pika.BlockingConnection(params)
            log.info(f"conectado a RabbitMQ en {RABBIT_HOST}:{RABBIT_PORT}")
            return connection
        except Exception as e:
            log.warning(f"RabbitMQ no disponible, reintentando en 5s: {e}")
            time.sleep(5)


# ── Punto de entrada ──────────────────────────────────────────────────────────

def consume():
    init_audit_table()

    connection = connect_rabbitmq()
    channel    = connection.channel()

    # declarar la cola como durable: sobrevive a reinicios de RabbitMQ
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    # procesar un mensaje a la vez para no saturar MySQL
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)

    log.info(f"escuchando cola '{QUEUE_NAME}' — esperando eventos...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("consumidor detenido")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    consume()
