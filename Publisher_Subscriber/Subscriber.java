import java.io.*;
import java.net.Socket;
import java.util.*;

/**
 * Subscriber - Cliente consumidor de mensajes del sistema de mensajería distribuida.
 *
 * Se conecta al Broker en localhost:5000, se suscribe aleatoriamente a entre
 * una y dos colas de las tres disponibles, y entra en un bucle continuo donde
 * solicita mensajes, calcula la suma de los números recibidos y devuelve el
 * resultado al Broker con el comando RES. Termina al recibir "STOP" o si
 * el Broker cierra la conexión.
 */
public class Subscriber {

    /**
     * Flujo de ejecución:
     *   1. Abre un socket hacia localhost:5000.
     *   2. Selecciona aleatoriamente 1 o 2 colas y envía "SUB cola1[,cola2]".
     *   3. En cada iteración elige una cola suscrita al azar, envía "GET cola"
     *      y procesa la respuesta:
     *        - null o "STOP"  -> sale del bucle limpiamente.
     *        - "EMPTY"        -> espera 200 ms y reintenta.
     *        - lista de nums  -> calcula la suma y la envía como "RES suma".
     *
     * @param args  Argumentos de línea de comandos (no utilizados).
     * @throws Exception Si ocurre un error al establecer la conexión inicial.
     */
    public static void main(String[] args) throws Exception {
        try (Socket s = new Socket("localhost", 5000);
             PrintWriter out = new PrintWriter(s.getOutputStream(), true);
             BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream()))) {
            
            Random r = new Random();
            List<String> allQueues = new ArrayList<>(List.of("primary", "secondary", "tertiary"));
            Collections.shuffle(allQueues);
            
            List<String> myQueues = allQueues.subList(0, r.nextBoolean() ? 1 : 2);
            out.println("SUB " + String.join(",", myQueues));
            System.out.println("[SUBSCRIBER] Suscrito a: " + myQueues);

            while (true) {
                String target = myQueues.get(r.nextInt(myQueues.size()));
                out.println("GET " + target);
                
                String response = in.readLine();
                
                // Si el Broker cierra o manda STOP, salimos limpiamente
                if (response == null || response.equals("STOP")) {
                    System.out.println("[SUBSCRIBER] El Broker indica fin de proceso.");
                    break;
                }

                if (!response.equals("EMPTY")) {
                    String clean = response.replaceAll("[\\[\\] ]", "");
                    int sum = Arrays.stream(clean.split(","))
                                   .mapToInt(Integer::parseInt)
                                   .sum();
                    
                    out.println("RES " + sum);
                    System.out.println("[SUBSCRIBER] Procesado: " + response + " | Suma enviada: " + sum);
                } else {
                    Thread.sleep(200); 
                }
            }
        } catch (IOException e) {
            System.out.println("[SUBSCRIBER] Conexión cerrada por el servidor.");
        } finally {
            System.out.println("[SUBSCRIBER] Finalizado.");
        }
    }
}