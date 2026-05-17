import java.io.*;
import java.net.Socket;
import java.util.*;

/**
 * Publisher - Cliente productor de mensajes del sistema de mensajería distribuida.
 *
 * Se conecta al Broker en 172.31.7.144:5000 y envía continuamente listas
 * de tres números aleatorios a una de las colas disponibles ("primary",
 * "secondary" o "tertiary"), usando la estrategia indicada por argumento.
 */
public class Publisher {

    /**
     * Lee el modo de operación desde args[0] (o usa "random" por defecto).
     * En cada iteración genera tres enteros aleatorios entre 0 y 99,
     * determina la cola destino con selectQueue() y envía el comando
     * "PUB cola|lista" al Broker. El bucle termina cuando el socket
     * detecta error de escritura o el Broker cierra la conexión.
     *
     * @param args  args[0] (opcional) - Modo de selección de cola:
     *              "random" (defecto), "weighted" o "conditional".
     * @throws Exception Si ocurre un error al establecer la conexión.
     */
    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "random";
        
        try (Socket s = new Socket("172.31.7.144", 5000);
             PrintWriter out = new PrintWriter(s.getOutputStream(), true)) {
            
            Random r = new Random();
            System.out.println("[PUBLISHER] Iniciado en modo: " + mode);

            while (true) {
                List<Integer> nums = Arrays.asList(r.nextInt(100), r.nextInt(100), r.nextInt(100));
                String queue = selectQueue(nums, mode, r);
                
                out.println("PUB " + queue + "|" + nums.toString());
                
                if (out.checkError()) break; // Detecta si el socket se cerró

                System.out.println("[PUBLISHER] Enviado " + nums + " a: " + queue);
                Thread.sleep(150); 
            }
        } catch (Exception e) {
            System.out.println("[PUBLISHER] El Broker ha finalizado la sesión.");
        } finally {
            System.out.println("[PUBLISHER] Proceso terminado.");
        }
    }

    /**
     * Determina la cola destino para un mensaje según la estrategia activa.
     *
     *   weighted    -> 50% a "primary", 30% a "secondary", 20% a "tertiary".
     *   conditional -> Si todos pares o todos impares: "tertiary".
     *                  Si dos pares: "primary". En otro caso: "secondary".
     *   random      -> Selección uniforme aleatoria entre las tres colas.
     *
     * @param nums  Lista de tres enteros del mensaje. Se usa para evaluar
     *              paridad en el modo "conditional".
     * @param mode  Modo de selección: "weighted", "conditional" o "random".
     * @param r     Instancia de Random compartida para valores aleatorios.
     * @return      Nombre de la cola: "primary", "secondary" o "tertiary".
     */
    private static String selectQueue(List<Integer> nums, String mode, Random r) {
        if (mode.equals("weighted")) {
            double p = r.nextDouble();
            if (p < 0.5) return "primary";
            if (p < 0.8) return "secondary";
            return "tertiary";
        } else if (mode.equals("conditional")) {
            long evens = nums.stream().filter(n -> n % 2 == 0).count();
            long odds = 3 - evens;
            if (evens == 3 || odds == 3) return "tertiary";
            return (evens == 2) ? "primary" : "secondary";
        }
        return List.of("primary", "secondary", "tertiary").get(r.nextInt(3));
    }
}