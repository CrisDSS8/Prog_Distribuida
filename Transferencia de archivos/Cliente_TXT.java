import java.net.*;
import java.io.*;
import java.util.Scanner;

public class Cliente_TXT {

    public static void main(String[] args) {
        try {
            Scanner sc = new Scanner(System.in);
            System.out.print("Nombre del archivo a solicitar: ");
            String nombreArchivo = sc.nextLine();

            InetAddress servidorIP = InetAddress.getByName("127.0.0.1");
            int puerto = 20000;

            DatagramSocket socket = new DatagramSocket();

            // ===== THREE-WAY HANDSHAKE =====
            enviar(socket, servidorIP, puerto, "SYN");
            esperar(socket, "SYN-ACK");
            enviar(socket, servidorIP, puerto, "ACK");

            // ===== Solicitud =====
            enviar(socket, servidorIP, puerto, "REQ|" + nombreArchivo);

            String respuesta = recibir(socket);
            if (respuesta.startsWith("ERROR")) {
                System.out.println("El archivo no existe en el servidor");
                socket.close();
                return;
            }

            BufferedWriter writer =
                new BufferedWriter(new FileWriter("copia_" + nombreArchivo));

            boolean activo = true;

            while (activo) {
                String mensaje = recibir(socket);

                if (mensaje.startsWith("DATA")) {
                    String[] partes = mensaje.split("\\|");
                    int seq = Integer.parseInt(partes[1]);
                    String linea = partes[2];

                    writer.write(linea);
                    writer.newLine();

                    enviar(socket, servidorIP, puerto, "ACK|" + seq);
                }
                else if (mensaje.equals("FIN")) {
                    enviar(socket, servidorIP, puerto, "ACK");
                    enviar(socket, servidorIP, puerto, "FIN");
                    esperar(socket, "ACK");
                    activo = false;
                }
            }

            writer.close();
            socket.close();
            System.out.println("Archivo recibido correctamente");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ===== FUNCIONES =====
    private static void enviar(DatagramSocket socket, InetAddress ip,
                               int puerto, String msj) throws IOException {
        byte[] datos = msj.getBytes();
        DatagramPacket packet =
            new DatagramPacket(datos, datos.length, ip, puerto);
        socket.send(packet);
    }

    private static String recibir(DatagramSocket socket) throws IOException {
        byte[] buffer = new byte[1024];
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
        socket.receive(packet);
        return new String(packet.getData(), 0, packet.getLength());
    }

    private static void esperar(DatagramSocket socket, String esperado)
            throws IOException {
        while (true) {
            if (recibir(socket).equals(esperado)) break;
        }
    }
}
