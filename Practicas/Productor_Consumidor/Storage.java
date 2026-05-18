import java.io.*;
import java.net.*;
import java.util.*;

/**
 * Clase Storage
 * Actúa como un servidor que almacena vectores enviados por productores,
 * los distribuye a consumidores y recibe los resultados procesados.
 */
public class Storage {

    private static List<int[]> vectores = Collections.synchronizedList(new ArrayList<>());
    private static List<Integer> resultados = Collections.synchronizedList(new ArrayList<>());
    private static Set<String> unicos = Collections.synchronizedSet(new HashSet<>());

    private static final int LIMITE = 100000;

    /**
     * Método principal del servidor Storage.
     * - Inicializa el servidor en el puerto 5000
     * - Atiende conexiones entrantes de productores y consumidores
     * - Finaliza cuando se alcanza el límite de resultados
     *
     * @param args Argumentos de línea de comandos (no utilizados)
     * @throws Exception En caso de errores en el servidor
     */
    public static void main(String[] args) throws Exception {
        ServerSocket servidor = new ServerSocket(5000);
        System.out.println("[STORAGE] Servidor iniciado en puerto 5000...");

        while (resultados.size() < LIMITE) {
            Socket cliente = servidor.accept();
            new Thread(() -> manejarCliente(cliente)).start();
        }

        servidor.close();

        long suma = resultados.stream().mapToLong(Integer::intValue).sum();

        System.out.println("\n===== RESULTADO FINAL =====");
        System.out.println("[STORAGE] Total resultados: " + resultados.size());
        System.out.println("[STORAGE] Suma total: " + suma);
    }

    /**
     * Maneja la comunicación con un cliente (productor o consumidor).
     * Dependiendo del mensaje recibido:
     * - "P:vector" → almacena un vector único
     * - "GET" → envía un vector disponible a un consumidor
     * - "R:resultado" → almacena el resultado procesado
     *
     * @param socket Socket del cliente conectado
     */
    private static void manejarCliente(Socket socket) {
        try (
            BufferedReader entrada = new BufferedReader(new InputStreamReader(socket.getInputStream()));
            PrintWriter salida = new PrintWriter(socket.getOutputStream(), true);
        ) {
            String mensaje = entrada.readLine();

            if (mensaje == null) return;

            if (mensaje.startsWith("P:")) {
                String vector = mensaje.substring(2);

                if (unicos.add(vector)) {
                    String[] partes = vector.split(",");
                    int[] v = Arrays.stream(partes).mapToInt(Integer::parseInt).toArray();
                    vectores.add(v);

                    System.out.println("[STORAGE] Vector recibido: " + vector);
                }
            }

            else if (mensaje.equals("GET")) {
                if (!vectores.isEmpty()) {
                    int[] v = vectores.remove(0);
                    salida.println(v[0] + "," + v[1] + "," + v[2]);

                    System.out.println("[STORAGE] Enviando vector al consumidor: " + Arrays.toString(v));
                }
            }

            else if (mensaje.startsWith("R:")) {
                int res = Integer.parseInt(mensaje.substring(2));
                resultados.add(res);

                if (resultados.size() % 100 == 0) {
                    System.out.println("[STORAGE] Total resultados: " + resultados.size());
                }

                System.out.println("[STORAGE] Resultado recibido: " + res);
            }

            socket.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}