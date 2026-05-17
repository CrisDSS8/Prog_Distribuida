import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * Broker - Servidor central del sistema de mensajería distribuida.
 *
 * Actúa como intermediario entre Publishers y Subscribers.
 * Mantiene tres colas de mensajes ("primary", "secondary", "tertiary"),
 * acepta conexiones entrantes en el puerto 5000 y gestiona los mensajes
 * PUB, SUB, GET y RES hasta alcanzar el límite de resultados configurado.
 */
public class Broker {
    private static final Map<String, Queue<String>> queues = new ConcurrentHashMap<>();
    private static final List<Integer> results = Collections.synchronizedList(new ArrayList<>());
    private static final Map<String, Set<String>> clientSubscriptions = new ConcurrentHashMap<>();
    private static final int MAX_RESULTS = 1000; 
    private static volatile boolean running = true;

    /**
     * Inicializa las tres colas de mensajes y abre un ServerSocket en el
     * puerto 5000. Por cada cliente que se conecta lanza un hilo dedicado
     * mediante handleClient().
     *
     * @param args  Argumentos de línea de comandos (no utilizados).
     * @throws Exception Si ocurre un error al abrir el socket del servidor.
     */
    public static void main(String[] args) throws Exception {
        queues.put("primary", new ConcurrentLinkedQueue<>());
        queues.put("secondary", new ConcurrentLinkedQueue<>());
        queues.put("tertiary", new ConcurrentLinkedQueue<>());

        try (ServerSocket server = new ServerSocket(5000)) {
            System.out.println("[BROKER] Esperando conexiones en puerto 5000...");

            while (running) {
                try {
                    Socket s = server.accept();
                    new Thread(() -> handleClient(s)).start();
                } catch (IOException e) {
                    if (!running) break;
                }
            }
        }
    }

    /**
     * Gestiona la comunicación con un cliente conectado. Lee líneas del
     * cliente y las despacha según el comando recibido:
     *
     *   PUB cola|dato   -> Encola el dato en la cola indicada.
     *   SUB cola1,cola2 -> Registra las suscripciones del cliente.
     *   GET cola        -> Extrae y devuelve el siguiente elemento,
     *                      o "EMPTY" si la cola está vacía.
     *   RES valor       -> Almacena el resultado; al llegar a MAX_RESULTS
     *                      envía "STOP" y llama a finish().
     *
     * @param s  Socket del cliente aceptado por el servidor.
     */
    private static void handleClient(Socket s) {
        String cid = s.getRemoteSocketAddress().toString();
        try (BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream()));
             PrintWriter out = new PrintWriter(s.getOutputStream(), true)) {
            
            String line;
            while (running && (line = in.readLine()) != null) {
                String[] p = line.split(" ", 2);
                if (p.length < 2) continue;

                switch (p[0]) {
                    case "PUB":
                        String[] dataPart = p[1].split("\\|");
                        queues.get(dataPart[0]).add(dataPart[1]);
                        break;
                    case "SUB":
                        clientSubscriptions.putIfAbsent(cid, new HashSet<>(Arrays.asList(p[1].split(","))));
                        break;
                    case "GET":
                        String data = queues.get(p[1]).poll();
                        out.println(data == null ? "EMPTY" : data);
                        break;
                    case "RES":
                        results.add(Integer.parseInt(p[1]));
                        if (results.size() % 10 == 0) {
                            System.out.println("[BROKER] Progreso: " + results.size() + " / " + MAX_RESULTS);
                        }
                        if (results.size() >= MAX_RESULTS) {
                            out.println("STOP");
                            finish();
                        }
                        break;
                }
            }
        } catch (Exception e) {
            // Conexión cerrada silenciosamente
        }
    }

    /**
     * Finaliza el sistema, imprime el reporte final y termina el proceso.
     *
     * Es idempotente: si ya fue invocado por otro hilo, retorna de inmediato.
     * Calcula la suma total de los resultados acumulados, muestra las
     * suscripciones de cada cliente y llama a System.exit().
     *
     * No recibe parámetros ni devuelve valor. Los datos provienen de los
     * campos estáticos results y clientSubscriptions.
     */
    private static void finish() {
        if (!running) return;
        running = false;
        long total = results.stream().mapToLong(i -> i).sum();
        System.out.println("\n========================================");
        System.out.println("            REPORTE FINAL");
        System.out.println("========================================");
        System.out.println("Suma Total de Resultados: " + total);
        System.out.println("Total de mensajes procesados: " + results.size());
        System.out.println("----------------------------------------");
        clientSubscriptions.forEach((id, subs) -> 
            System.out.println("Cliente: " + id + " | Suscrito a: " + subs));
        System.out.println("========================================\n");
        System.out.println("[BROKER] Sistema finalizado exitosamente.");
        System.exit(0);
    }
}