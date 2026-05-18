import java.io.*;
import java.net.*;

/**
 * Clase Consumidor
 * Se encarga de solicitar vectores al Storage, procesarlos
 * (sumando sus valores) y enviar el resultado nuevamente al Storage.
 */
public class Consumidor {

    /**
     * Método principal que ejecuta el consumidor.
     * Realiza las siguientes acciones en bucle infinito:
     * - Solicita un vector al Storage mediante "GET"
     * - Procesa el vector recibido
     * - Envía el resultado al Storage
     *
     * @param args Argumentos de línea de comandos (no utilizados)
     * @throws Exception En caso de errores de conexión o interrupciones
     */
    public static void main(String[] args) throws Exception {

        while (true) {

            try {
                Socket socket = new Socket("172.31.1.214", 5000);
                BufferedReader entrada = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                PrintWriter salida = new PrintWriter(socket.getOutputStream(), true);

                salida.println("GET");

                String respuesta = entrada.readLine();
                socket.close();

                if (respuesta != null) {
                    System.out.println("[CONSUMIDOR] Vector recibido: " + respuesta);

                    String[] partes = respuesta.split(",");
                    int a = Integer.parseInt(partes[0]);
                    int b = Integer.parseInt(partes[1]);
                    int c = Integer.parseInt(partes[2]);

                    int resultado = a + b + c;

                    System.out.println("[CONSUMIDOR] Resultado calculado: " + resultado);

                    Socket socket2 = new Socket("172.31.1.214", 5000);
                    PrintWriter salida2 = new PrintWriter(socket2.getOutputStream(), true);

                    System.out.println("[CONSUMIDOR] Enviando resultado...");

                    salida2.println("R:" + resultado);

                    socket2.close();
                }

                Thread.sleep(10); 

            } catch (Exception e) {
                System.out.println("[CONSUMIDOR] Storage no disponible. Finalizando...");
                break;
            }
        }
    }
}