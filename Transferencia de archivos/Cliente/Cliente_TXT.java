import java.io.*;
import java.net.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Scanner;

public class Cliente_TXT {

    private static BufferedWriter writer = null;
    private static BufferedWriter logCliente;
    private static final int BUFFER = 1024;
    private static final DateTimeFormatter FORMATO_FECHA = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public static void main(String[] args) {
        try {
            InetAddress ipServidor = InetAddress.getByName("172.31.10.150");
            int puertoServidor = 20000;

            DatagramSocket socket = new DatagramSocket();
            System.out.println("Cliente iniciado");

            logCliente = new BufferedWriter(new FileWriter("log_cliente.txt", true));
            log(logCliente, "[CLIENTE] Cliente iniciado");

            // Solicitud del archivo
            Scanner sc = new Scanner(System.in);
            System.out.print("¿Qué archivo desea?: ");
            String archivoSolicitado = sc.nextLine();

            if (!archivoSolicitado.endsWith(".txt")) {
                archivoSolicitado += ".txt";
            }

            enviar(socket, archivoSolicitado, ipServidor, puertoServidor);
            log(logCliente, "[CLIENTE] Archivo solicitado: " + archivoSolicitado);

            // ===== THREE-WAY HANDSHAKE =====
            String respuesta = recibir(socket);

            if (!respuesta.startsWith("SYN:")) {
                log(logCliente, "[CLIENTE] Respuesta inesperada: " + respuesta);
                socket.close();
                return;
            }

            // SYN:puertoTransferencia:seqInicial
            String[] partesSyn = respuesta.split(":");
     
            if (partesSyn.length < 3) {
                System.out.println("Formato SYN inválido: " + respuesta);
                socket.close();
                return;
            }

            int puertoTransferencia = Integer.parseInt(partesSyn[1]);
            int seqInicial = Integer.parseInt(partesSyn[2]);

            System.out.println("Puerto de transferencia " /*+ puertoTransferencia*/);
            System.out.println("SEQ inicial recibida " /*+ seqInicial*/);

            log(logCliente, "[CLIENTE] Puerto de transferencia recibido " /*+ puertoTransferencia*/);
            log(logCliente, "[CLIENTE] SEQ inicial recibida " /*+ seqInicial*/);

            enviar(socket, "ACK", ipServidor, puertoTransferencia);
            log(logCliente, "[CLIENTE] -> ACK enviado");

            // ===== RECEPCIÓN DEL ARCHIVO =====
            int seqEsperado = -1;

            while (true) {
                String msg = recibir(socket);

                if (msg.equals("EOF")) {
                    enviar(socket, "ACK:EOF", ipServidor, puertoTransferencia);
                    log(logCliente, "[CLIENTE] <- EOF recibido");
                    log(logCliente, "[CLIENTE] -> ACK:EOF enviado");
                    break;
                }

                if (msg.startsWith("ERROR")) {
                    log(logCliente, "[CLIENTE] " + msg);

                    String fin = recibir(socket);
                    if (fin.equals("FIN")) {
                        log(logCliente, "[CLIENTE] <- FIN recibido");
                        enviar(socket, "ACK:FIN", ipServidor, puertoTransferencia);
                        enviar(socket, "FIN", ipServidor, puertoTransferencia);
                        recibir(socket); // ACK:FIN
                    }
                    socket.close();
                    return;
                }

                String[] partes = msg.split(":", 2);
                int seq = Integer.parseInt(partes[0]);
                String linea = partes[1];

                log(logCliente, "[CLIENTE] <- SEQ recibido: " + seq);

                if (seqEsperado == -1) {
                    seqEsperado = seq;
                }

                if (seq == seqEsperado) {
                    if (writer == null) {
                        writer = new BufferedWriter(new FileWriter("Copia_" + archivoSolicitado));
                        log(logCliente, "[CLIENTE] Archivo creado: Copia_" + archivoSolicitado);
                    }

                    log(logCliente, "[CLIENTE] Línea aceptada: " + seq + ":" + linea);
                    writer.write(linea);
                    writer.newLine();
                    seqEsperado++;

                } else {
                    log(logCliente, "[CLIENTE] SEQ inesperado. Esperado: "
                        + seqEsperado + " | Recibido: " + seq);
                }

                enviar(socket, "ACK:" + seq, ipServidor, puertoTransferencia);
            }

            if (writer != null) {
                writer.close();
            }

            // ===== FOUR-WAY HANDSHAKE =====
            String fin = recibir(socket);
            if (fin.equals("FIN")) {
                enviar(socket, "ACK:FIN", ipServidor, puertoTransferencia);
                enviar(socket, "FIN", ipServidor, puertoTransferencia);
                recibir(socket); // ACK:FIN

                log(logCliente, "[CLIENTE] <- FIN recibido");
                log(logCliente, "[CLIENTE] -> ACK:FIN enviado");
                log(logCliente, "[CLIENTE] -> FIN enviado");
                log(logCliente, "[CLIENTE] <- ACK:FIN recibido");
            }

            log(logCliente, "[CLIENTE] Conexión finalizada");
            logCliente.close();
            socket.close();

            System.out.println("Transferencia finalizada");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ===== FUNCIONES AUXILIARES =====

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);

        log(logCliente, "[CLIENTE] -> ENVIANDO: \"" + msg/* +
            "\" a " + ip.getHostAddress() + ":" + puerto*/);

        socket.send(p);
    }

    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);

        String msg = new String(p.getData(), 0, p.getLength()).trim();

        log(logCliente, "[CLIENTE] <- RECIBIDO: \"" + msg /*+
            "\" desde " + p.getAddress().getHostAddress() +
            ":" + p.getPort()*/);

        return msg;
    }

    private static synchronized void log(BufferedWriter log, String msg) throws IOException {
        String fechaHora = LocalDateTime.now().format(FORMATO_FECHA);
        log.write("[" + fechaHora + "] " + msg);
        log.newLine();
        log.flush();
    }
}
