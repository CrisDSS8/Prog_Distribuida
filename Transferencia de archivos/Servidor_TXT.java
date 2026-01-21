import java.io.*;
import java.net.*;
import java.util.concurrent.*;

public class Servidor_TXT {

    private static final int PUERTO = 20000;
    private static final int BUFFER = 1024;
    private static final String CARPETA =
            "C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Archivos compartidos/Textos txt/";

    private static ExecutorService pool = Executors.newCachedThreadPool();

    public static void main(String[] args) throws Exception {

        DatagramSocket socketEscucha = new DatagramSocket(PUERTO);
        System.out.println("Servidor UDP iniciado en puerto " + PUERTO);

        while (true) {
            byte[] buffer = new byte[BUFFER];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            socketEscucha.receive(packet);

            pool.execute(() -> manejarCliente(packet));
        }
    }

    private static void manejarCliente(DatagramPacket packet) {
        try {
            InetAddress ipCliente = packet.getAddress();
            int puertoCliente = packet.getPort();
            String archivo = new String(packet.getData(), 0, packet.getLength()).trim();

            // SOCKET EXCLUSIVO PARA ESTE CLIENTE
            DatagramSocket socketCliente = new DatagramSocket();
            int puertoTransferencia = socketCliente.getLocalPort();

            // --- THREE WAY HANDSHAKE ---
            enviar(socketCliente, "SYN:" + puertoTransferencia, ipCliente, puertoCliente);
            if (!esperar(socketCliente, "ACK")) {
                socketCliente.close();
                return;
            }

            enviarArchivoUDP(socketCliente, ipCliente, puertoCliente, archivo);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ==========================================================
    // FUNCIÓN EXIGIDA POR LA CONSIGNA
    // ==========================================================
    public static void enviarArchivoUDP(
            DatagramSocket socket,
            InetAddress ipDestino,
            int puertoDestino,
            String nombreArchivo) throws Exception {

        File archivo = new File(CARPETA + nombreArchivo);

        if (!archivo.exists()) {
            enviar(socket, "ERROR:ARCHIVO_NO_EXISTE", ipDestino, puertoDestino);
            socket.close();
            return;
        }

        BufferedReader reader = new BufferedReader(new FileReader(archivo));
        String linea;
        int seq = 0;

        while ((linea = reader.readLine()) != null) {
            boolean ok = false;
            while (!ok) {
                enviar(socket, seq + ":" + linea, ipDestino, puertoDestino);
                ok = esperar(socket, "ACK:" + seq);
            }
            seq++;
        }
        reader.close();

        enviar(socket, "EOF", ipDestino, puertoDestino);
        esperar(socket, "ACK:EOF");

        // --- FOUR WAY HANDSHAKE ---
        enviar(socket, "FIN", ipDestino, puertoDestino);
        esperar(socket, "ACK:FIN");
        esperar(socket, "FIN");
        enviar(socket, "ACK:FIN", ipDestino, puertoDestino);

        socket.close();
    }

    // ==========================================================
    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        socket.send(new DatagramPacket(data, data.length, ip, puerto));
    }

    private static boolean esperar(DatagramSocket socket, String esperado) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);
        String r = new String(p.getData(), 0, p.getLength()).trim();
        return r.equals(esperado);
    }
}
