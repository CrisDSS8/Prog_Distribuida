import java.io.*;
import java.net.*;

public class Cliente_TXT {

    private static final int BUFFER = 1024;

    public static void main(String[] args) throws Exception {

        InetAddress ipServidor = InetAddress.getByName("127.0.0.1");
        int puertoServidor = 5000;

        DatagramSocket socket = new DatagramSocket();

        String archivoSolicitado = "ejemplo.txt";
        enviar(socket, archivoSolicitado, ipServidor, puertoServidor);

        esperar(socket, "SYN");
        enviar(socket, "ACK", ipServidor, puertoServidor);

        String respuesta = recibir(socket);
        if (respuesta.startsWith("ERROR")) {
            System.out.println(respuesta);
            cerrar(socket, ipServidor, puertoServidor);
            return;
        }

        BufferedWriter writer =
                new BufferedWriter(new FileWriter("copia_" + archivoSolicitado));

        while (true) {
            String msg = recibir(socket);

            if (msg.equals("EOF")) {
                enviar(socket, "ACK:EOF", ipServidor, puertoServidor);
                break;
            }

            String[] p = msg.split(":", 2);
            writer.write(p[1]);
            writer.newLine();
            enviar(socket, "ACK:" + p[0], ipServidor, puertoServidor);
        }
        writer.close();

        cerrar(socket, ipServidor, puertoServidor);
    }

    private static void cerrar(DatagramSocket socket, InetAddress ip, int puerto) throws Exception {
        esperar(socket, "FIN");
        enviar(socket, "ACK:FIN", ip, puerto);
        enviar(socket, "FIN", ip, puerto);
        esperar(socket, "ACK:FIN");
        socket.close();
    }

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        socket.send(new DatagramPacket(data, data.length, ip, puerto));
    }

    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);
        return new String(p.getData()).trim();
    }

    private static void esperar(DatagramSocket socket, String esperado) throws Exception {
        while (!recibir(socket).equals(esperado));
    }
}
