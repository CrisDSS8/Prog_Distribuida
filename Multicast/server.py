import socket
import json
import time
import threading
import uuid
import sys
from collections import Counter

MULTICAST_GROUP    = '224.1.1.1'
MULTICAST_PORT     = 5007
SERVER_HOST        = '127.0.0.1'
SERVER_LISTEN_PORT = 5008
CLIENT_PORT        = 5009
NUM_REPLICAS       = 3
BUFFER_SIZE        = 4096
TIMEOUT            = 10.0

POLICY_FIRST    = 1
POLICY_ALL      = 2
POLICY_MAJORITY = 3


class RequestState:
    """
    Representa el estado de una petición en vuelo dentro del servidor.

    Atributos:
        request_id  (str):            Identificador único de la petición (UUID).
        client_addr (tuple):          Dirección (IP, puerto) del cliente.
        policy      (int):            Política de entrega activa.
        responses   (list):           Lista de tuplas (replica_id, resultado) recibidas.
        answered    (bool):           Indica si ya se respondió al cliente.
        start_time  (float):          Timestamp de cuando se recibió la petición.
        lock        (threading.Lock): Lock para acceso seguro desde múltiples hilos.
    """

    def __init__(self, request_id, client_addr, policy):
        """
        Inicializa el estado de una nueva petición.

        Parámetros:
            request_id  (str):   UUID que identifica la petición.
            client_addr (tuple): Dirección (IP, puerto) del cliente.
            policy      (int):   Política de entrega seleccionada.

        Retorna:
            None
        """
        self.request_id  = request_id
        self.client_addr = client_addr
        self.policy      = policy
        self.responses   = []
        self.answered    = False
        self.start_time  = time.time()
        self.lock        = threading.Lock()


class MulticastServer:
    """
    Servidor principal del sistema MCD Multicast.

    Recibe vectores de clientes vía UDP, los distribuye a las réplicas
    mediante multicast y aplica la política de entrega configurada para
    decidir cuándo responder al cliente.
    """

    def __init__(self, policy):
        """
        Inicializa el servidor con la política de entrega indicada y
        crea todos los sockets necesarios para la comunicación.

        Parámetros:
            policy (int): Política de entrega.
                          1 = FIRST     -> responde con la primera réplica que llegue.
                          2 = ALL_EQUAL -> responde cuando las 3 réplicas coinciden.
                          3 = MAJORITY  -> responde cuando al menos 2 de 3 coinciden.

        Retorna:
            None
        """
        self.policy  = policy
        self.pending = {}
        self.p_lock  = threading.Lock()
        self.running = True

        self.mc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mc_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        self.rep_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rep_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rep_sock.bind(('', SERVER_LISTEN_PORT))
        self.rep_sock.settimeout(1.0)

        self.cli_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cli_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cli_sock.bind(('', CLIENT_PORT))
        self.cli_sock.settimeout(1.0)

        self.ans_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[Servidor] Política: {['','FIRST','ALL_EQUAL','MAJORITY'][policy]}")

    def _check_policy(self, responses):
        """
        Evalúa si las respuestas recibidas de las réplicas satisfacen
        la política de entrega activa y determina el resultado final.

        Parámetros:
            responses (list[tuple]): Lista de (replica_id, resultado) recibidos hasta ahora.

        Retorna:
            tuple(bool, int | None):
                - (True, valor) -> se puede responder al cliente con ese valor.
                - (True, None)  -> se puede responder pero no hubo consenso.
                - (False, None) -> aún no se cumplen las condiciones para responder.
        """
        n = len(responses)

        if self.policy == POLICY_FIRST and n >= 1:
            return True, responses[0][1]

        elif self.policy == POLICY_ALL and n == NUM_REPLICAS:
            vals = [r[1] for r in responses]
            return True, (vals[0] if len(set(vals)) == 1 else None)

        elif self.policy == POLICY_MAJORITY and n >= (NUM_REPLICAS // 2 + 1):
            vals = [r[1] for r in responses]
            mc, cnt = Counter(vals).most_common(1)[0]
            return True, (mc if cnt >= NUM_REPLICAS // 2 + 1 else None)

        return False, None

    def _on_replica(self, data):
        """
        Procesa el mensaje de respuesta enviado por una réplica.
        Actualiza el estado de la petición y, si la política lo permite,
        envía la respuesta final al cliente.

        Parámetros:
            data (bytes): Mensaje JSON de la réplica con los campos
                          request_id, replica_id y result.

        Retorna:
            None
        """
        try:
            msg = json.loads(data.decode())
        except:
            return

        with self.p_lock:
            state = self.pending.get(msg['request_id'])
        if not state:
            return

        with state.lock:
            if state.answered:
                return
            state.responses.append((msg['replica_id'], msg['result']))
            can, val = self._check_policy(state.responses)
            if can:
                state.answered = True
                elapsed = time.time() - state.start_time
                resp = {
                    'status':             'ok' if val is not None else 'no_consensus',
                    'result':             val,
                    'policy':             self.policy,
                    'responses_received': len(state.responses),
                    'elapsed_ms':         round(elapsed * 1000, 2)
                }
                self.ans_sock.sendto(json.dumps(resp).encode(), state.client_addr)
                with self.p_lock:
                    self.pending.pop(msg['request_id'], None)

    def _on_client(self, data, addr):
        """
        Procesa una petición entrante de un cliente.
        Valida el vector, registra la petición como pendiente y la
        distribuye a las réplicas vía multicast.

        Parámetros:
            data (bytes): Mensaje JSON del cliente con el campo 'numbers'
                          (lista de exactamente 5 enteros).
            addr (tuple): Dirección (IP, puerto) del cliente remitente.

        Retorna:
            None
        """
        try:
            msg     = json.loads(data.decode())
            numbers = msg['numbers']
            assert len(numbers) == 5
        except:
            self.ans_sock.sendto(
                json.dumps({'status': 'error', 'message': 'Se requieren 5 números'}).encode(),
                addr
            )
            return

        rid   = str(uuid.uuid4())
        state = RequestState(rid, addr, self.policy)

        with self.p_lock:
            self.pending[rid] = state

        task = {
            'request_id':  rid,
            'numbers':     numbers,
            'server_host': SERVER_HOST,
            'server_port': SERVER_LISTEN_PORT
        }
        self.mc_sock.sendto(json.dumps(task).encode(), (MULTICAST_GROUP, MULTICAST_PORT))
        print(f"[Servidor] Tarea {rid[:8]} enviada: {numbers}")

    def _timeout_loop(self):
        """
        Hilo de vigilancia que revisa periódicamente las peticiones pendientes.
        Si alguna supera el tiempo límite definido en TIMEOUT sin haber recibido
        suficientes respuestas, notifica al cliente con un mensaje de timeout.

        Parámetros:
            None

        Retorna:
            None: Corre en bucle infinito mientras self.running sea True.
        """
        while self.running:
            time.sleep(1.0)
            now = time.time()
            with self.p_lock:
                expired = [(rid, s) for rid, s in self.pending.items()
                           if now - s.start_time > TIMEOUT]
            for rid, state in expired:
                with state.lock:
                    if not state.answered:
                        state.answered = True
                        self.ans_sock.sendto(
                            json.dumps({'status': 'timeout'}).encode(),
                            state.client_addr
                        )
                with self.p_lock:
                    self.pending.pop(rid, None)

    def run(self):
        """
        Arranca el servidor lanzando tres hilos en paralelo:
            - rep_loop:      escucha respuestas UDP de las réplicas.
            - cli_loop:      escucha peticiones UDP de los clientes.
            - _timeout_loop: vigila peticiones que superan el tiempo límite.

        El hilo principal queda bloqueado hasta recibir Ctrl+C.

        Parámetros:
            None

        Retorna:
            None
        """
        def rep_loop():
            """Escucha respuestas de las réplicas y las procesa en hilos separados."""
            while self.running:
                try:
                    data, _ = self.rep_sock.recvfrom(BUFFER_SIZE)
                    threading.Thread(target=self._on_replica, args=(data,), daemon=True).start()
                except socket.timeout:
                    pass

        def cli_loop():
            """Escucha peticiones de los clientes y las procesa en hilos separados."""
            while self.running:
                try:
                    data, addr = self.cli_sock.recvfrom(BUFFER_SIZE)
                    threading.Thread(target=self._on_client, args=(data, addr), daemon=True).start()
                except socket.timeout:
                    pass

        for fn in (rep_loop, cli_loop, self._timeout_loop):
            threading.Thread(target=fn, daemon=True).start()

        print("[Servidor] Listo. Ctrl+C para detener.")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.running = False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python server.py <1|2|3>")
        print("  1=FIRST  2=ALL_EQUAL  3=MAJORITY")
        sys.exit(1)
    MulticastServer(int(sys.argv[1])).run()