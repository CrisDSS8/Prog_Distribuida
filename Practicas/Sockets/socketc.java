import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.SocketTimeoutException;
import java.util.Scanner;

public class socketc {

    public static void main(String[] args) {
        try {
            Scanner scanner = new Scanner(System.in);
            
            InetAddress ipServidor = InetAddress.getByName("172.31.2.216");
            int puertoServidor = 20000;

            DatagramSocket socket = new DatagramSocket();
            socket.setSoTimeout(1000); 

            System.out.println("Cliente UDP iniciado (timeout 1s)");
            System.out.println("Comandos: LIST | salir\n");

            while (true) {
                System.out.print("Mensaje a enviar: ");
                String mensaje = scanner.nextLine();

                byte[] datos = mensaje.getBytes(java.nio.charset.StandardCharsets.UTF_8);

                DatagramPacket paquete = new DatagramPacket(
                        datos,
                        datos.length,
                        ipServidor,
                        puertoServidor
                );

                socket.send(paquete);

                // Salida del cliente
                if (mensaje.equalsIgnoreCase("salir")) {
                    System.out.println("Conexión terminada por el cliente.");
                    break;
                }

                try {
                    // Recibe respuesta del servidor
                    byte[] buffer = new byte[1024];
                    DatagramPacket respuesta = new DatagramPacket(buffer, buffer.length);
                    socket.receive(respuesta);

                    String mensajeRespuesta = new String(
                            respuesta.getData(),
                            0,
                            respuesta.getLength(),
                            java.nio.charset.StandardCharsets.UTF_8
                    );

                    System.out.println("Respuesta del servidor:");
                    System.out.println(mensajeRespuesta);

                } catch (SocketTimeoutException e) {
                    System.out.println("Timeout: el servidor no respondió");
                    System.out.println("Puedes enviar otro mensaje\n");
                    continue; 
                }
            }

            socket.close();
            scanner.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}