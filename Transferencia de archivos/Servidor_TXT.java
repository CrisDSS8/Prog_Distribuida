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

            DatagramSocket socketCliente = new DatagramSocket();
            int puertoTransferencia = socketCliente.getLocalPort();

            //THREE-WAY HANDSHAKE
            System.out.println("[SERVIDOR] -> SYN enviado (puerto " + puertoTransferencia + ")");
            enviar(socketCliente, "SYN:" + puertoTransferencia, ipCliente, puertoCliente);

            if (!esperar(socketCliente, "ACK")) {
                System.out.println("[SERVIDOR] <- ACK no recibido. Cancelando conexión");
                socketCliente.close();
                return;
            }

            System.out.println("[SERVIDOR] <- ACK recibido. Conexión establecida");

            enviarArchivoUDP(socketCliente, ipCliente, puertoCliente, archivo);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void enviarArchivoUDP(
            DatagramSocket socket,
            InetAddress ipDestino,
            int puertoDestino,
            String nombreArchivo) throws Exception {

        File archivo = new File(CARPETA + nombreArchivo);

        if (!archivo.exists()) {
            System.out.println("[SERVIDOR] ERROR: archivo no existe");
            enviar(socket, "ERROR:ARCHIVO_NO_EXISTE", ipDestino, puertoDestino);
            cerrar(socket, ipDestino, puertoDestino);
            socket.close();
            return;
        }

        BufferedReader reader = new BufferedReader(new FileReader(archivo));
        String linea;
        int seq = 0;

        while ((linea = reader.readLine()) != null) {
            boolean ok = false;
            while (!ok) {
                System.out.println("[SERVIDOR] -> SEQ=" + seq + " | " + linea);
                enviar(socket, seq + ":" + linea, ipDestino, puertoDestino);

                System.out.println("[SERVIDOR] <- Esperando ACK:" + seq);
                ok = esperar(socket, "ACK:" + seq);

                if (ok) {
                    System.out.println("[SERVIDOR] <- ACK:" + seq + " recibido");
                }
            }
            seq++;
        }
        reader.close();

        System.out.println("[SERVIDOR] -> EOF enviado");
        enviar(socket, "EOF", ipDestino, puertoDestino);

        esperar(socket, "ACK:EOF");
        System.out.println("[SERVIDOR] <- ACK:EOF recibido");


        //FOUR-WAY HANDSHAKE
        cerrar(socket, ipDestino, puertoDestino);

        socket.close();
    }

    private static void cerrar(DatagramSocket socket, InetAddress ipDestino, int puertoDestino) throws Exception {
        System.out.println("[SERVIDOR] -> FIN enviado");
        enviar(socket, "FIN", ipDestino, puertoDestino);

        esperar(socket, "ACK:FIN");
        System.out.println("[SERVIDOR] <- ACK:FIN recibido");

        esperar(socket, "FIN");
        System.out.println("[SERVIDOR] <- FIN recibido");

        enviar(socket, "ACK:FIN", ipDestino, puertoDestino);
        System.out.println("[SERVIDOR] -> ACK:FIN enviado");
    }

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
