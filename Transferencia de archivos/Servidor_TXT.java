import java.io.*;
import java.net.*;
import java.util.concurrent.*;

public class Servidor_TXT {

    private static final int PUERTO = 5000;
    private static final int BUFFER = 1024;
    private static final String CARPETA = "archivos_servidor/";

    private static ExecutorService pool = Executors.newCachedThreadPool();

    public static void main(String[] args) throws Exception {

        DatagramSocket socket = new DatagramSocket(PUERTO);
        System.out.println("Servidor UDP activo...");

        while (true) {
            byte[] buffer = new byte[BUFFER];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            socket.receive(packet);

            pool.execute(() -> {
                try {
                    InetAddress ipCliente = packet.getAddress();
                    InetAddress ipServidor = InetAddress.getLocalHost();
                    int puertoCliente = packet.getPort();
                    String archivo = new String(packet.getData()).trim();

                    enviarArchivoUDP(ipServidor, ipCliente, puertoCliente, archivo);

                } catch (Exception e) {
                    e.printStackTrace();
                }
            });
        }
    }

    // ==========================================================
    // FUNCIÓN EXIGIDA POR LA CONSIGNA
    // ==========================================================
    public static void enviarArchivoUDP(
            InetAddress ipOrigen,
            InetAddress ipDestino,
            int puertoDestino,
            String nombreArchivo) throws Exception {

        DatagramSocket socket = new DatagramSocket();
        File archivo = new File(CARPETA + nombreArchivo);

        // --- THREE WAY HANDSHAKE ---
        enviar(socket, "SYN", ipDestino, puertoDestino);
        if (!esperar(socket, "ACK")) return;

        // --- VALIDAR ARCHIVO ---
        if (!archivo.exists()) {
            enviar(socket, "ERROR:ARCHIVO_NO_EXISTE", ipDestino, puertoDestino);
            cerrar(socket, ipDestino, puertoDestino);
            return;
        }

        BufferedReader reader = new BufferedReader(new FileReader(archivo));
        String linea;
        int seq = 0;

        // --- ENVÍO CONFIABLE ---
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
        cerrar(socket, ipDestino, puertoDestino);
    }

    // ==========================================================
    // MÉTODOS AUXILIARES
    // ==========================================================
    private static void cerrar(DatagramSocket socket, InetAddress ip, int puerto) throws Exception {
        enviar(socket, "FIN", ip, puerto);
        esperar(socket, "ACK:FIN");
        esperar(socket, "FIN");
        enviar(socket, "ACK:FIN", ip, puerto);
        socket.close();
    }

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);
        socket.send(p);
    }

    private static boolean esperar(DatagramSocket socket, String esperado) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);
        String recibido = new String(p.getData()).trim();
        return recibido.equals(esperado);
    }
}
