import java.io.*;
import java.net.*;

public class Cliente_TXT {

    private static final int BUFFER = 1024;

    public static void main(String[] args) {
        try {
            InetAddress ipServidor = InetAddress.getByName("127.0.0.1");
            int puertoServidor = 20000;

            DatagramSocket socket = new DatagramSocket();
            System.out.println("Cliente iniciado");

            // ===== PASO 1: ENVIAR NOMBRE DEL ARCHIVO =====
            String archivoSolicitado = "Lorem Ipsum.txt";
            enviar(socket, archivoSolicitado, ipServidor, puertoServidor);
            System.out.println("Archivo solicitado: " + archivoSolicitado);

            // ===== PASO 2: ESPERAR SYN:PUERTO =====
            String respuesta = recibir(socket);
            if (!respuesta.startsWith("SYN:")) {
                System.out.println("Respuesta inesperada: " + respuesta);
                socket.close();
                return;
            }

            int puertoTransferencia =
                    Integer.parseInt(respuesta.split(":")[1]);

            System.out.println("Puerto de transferencia recibido: " + puertoTransferencia);

            // ===== PASO 3: ACK AL NUEVO PUERTO =====
            enviar(socket, "ACK", ipServidor, puertoTransferencia);

            BufferedWriter writer =
                    new BufferedWriter(new FileWriter("copia_" + archivoSolicitado));

            // ===== PASO 4: RECEPCIÓN DEL ARCHIVO =====
            while (true) {
                String msg = recibir(socket);

                if (msg.equals("EOF")) {
                    enviar(socket, "ACK:EOF", ipServidor, puertoTransferencia);
                    break;
                }

                if (msg.startsWith("ERROR")) {
                    System.out.println(msg);
                    break;
                }

                String[] partes = msg.split(":", 2);
                writer.write(partes[1]);
                writer.newLine();

                enviar(socket, "ACK:" + partes[0], ipServidor, puertoTransferencia);
            }

            writer.close();

            // ===== PASO 5: FOUR WAY HANDSHAKE =====
            String fin = recibir(socket);
            if (fin.equals("FIN")) {
                enviar(socket, "ACK:FIN", ipServidor, puertoTransferencia);
                enviar(socket, "FIN", ipServidor, puertoTransferencia);
                recibir(socket); // ACK:FIN
            }

            socket.close();
            System.out.println("Transferencia finalizada");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);
        socket.send(p);
    }

    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);
        return new String(p.getData(), 0, p.getLength()).trim();
    }
}
