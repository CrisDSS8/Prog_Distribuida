import java.io.*;
import java.net.*;
import java.util.*;

/**
 * Clase Productor
 * Se encarga de generar vectores aleatorios de tres números
 * y enviarlos al Storage mediante sockets TCP.
 */
public class Productor {

    /**
     * Método principal que ejecuta el productor.
     * Genera continuamente vectores aleatorios en el rango [1,1000]
     * y los envía al Storage con el prefijo "P:".
     *
     * @param args Argumentos de línea de comandos (no utilizados)
     * @throws Exception En caso de errores de conexión o interrupciones
     */
    public static void main(String[] args) throws Exception {
        Random random = new Random();

        while (true) {
            int a = random.nextInt(1000) + 1;
            int b = random.nextInt(1000) + 1;
            int c = random.nextInt(1000) + 1;

            String vector = a + "," + b + "," + c;

            try {
                Socket socket = new Socket("localhost", 5000);
                PrintWriter salida = new PrintWriter(socket.getOutputStream(), true);

                System.out.println("[PRODUCTOR] Enviando vector: " + vector);

                salida.println("P:" + vector);

                socket.close();

                Thread.sleep(10); 

            }  catch (Exception e) {
                System.out.println("[PRODUCTOR] Storage no disponible. Finalizando...");
                break; 
            }
        }
    }
}