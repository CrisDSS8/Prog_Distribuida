import TLS.AESUtils;
import java.io.*;
import java.net.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Scanner;
import javax.crypto.SecretKey;

public class Cliente_TXT {

    private static BufferedWriter writer = null;
    private static BufferedWriter logCliente;
    private static final int BUFFER = 1024;
    private static SecretKey claveSesion;
    private static final DateTimeFormatter FORMATO_FECHA = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public static void main(String[] args) {
        try {
            InetAddress ipServidor = InetAddress.getByName("172.31.0.161");
            int puertoServidor = 20000;

            DatagramSocket socket = new DatagramSocket();
            socket.setSoTimeout(3000);

            System.out.println("Cliente iniciado");

            logCliente = new BufferedWriter(new FileWriter("log_cliente.txt", true));
            log(logCliente, "[CLIENTE] Cliente iniciado");

            // nombre del archivo a solicitar
            Scanner sc = new Scanner(System.in);
            System.out.print("¿Qué archivo desea?: ");
            String archivoSolicitado = sc.nextLine();
            sc.close();

            if (!archivoSolicitado.endsWith(".txt")) {
                archivoSolicitado += ".txt";
            }

            enviar(socket, archivoSolicitado, ipServidor, puertoServidor);
            log(logCliente, "[CLIENTE] Archivo solicitado: " + archivoSolicitado);

            // espera SYN
            String respuesta = recibir(socket);
            log(logCliente, "[CLIENTE] <- SYN recibido: " + respuesta);

            if (!respuesta.startsWith("SYN:")) {
                log(logCliente, "[CLIENTE] Respuesta inesperada: "  + respuesta);
                socket.close();
                return;
            }

            // FORMATO: SYN:puerto:SEQ
            String[] partesSyn = respuesta.split(":");

            if (partesSyn.length < 3) {
                System.out.println("Formato SYN inválido: " + respuesta);
                socket.close();
                return;
            }

            int puertoTransferencia = Integer.parseInt(partesSyn[1]);
            int seqInicial = Integer.parseInt(partesSyn[2]);

            log(logCliente, "[CLIENTE] Puerto transferencia " /*+ puertoTransferencia*/);
            log(logCliente, "[CLIENTE] SEQ inicial servidor: " + seqInicial);

            // ACK del handshake UDP 
            enviar(socket, "ACK", ipServidor, puertoTransferencia);
            log(logCliente, "[CLIENTE] -> ACK enviado");

            // Handshake TLS
            String tlsMsg = recibir(socket);

            if (!tlsMsg.startsWith("TLS_KEY:")) {
                throw new Exception("Handshake TLS inválido");
            }

            String claveBase64 = tlsMsg.substring(8);
            claveSesion = AESUtils.stringToClave(claveBase64);

            enviar(socket, "TLS_ACK", ipServidor, puertoTransferencia);
            log(logCliente, "[CLIENTE] -> TLS_ACK enviado");

            // Recive el archivo
            int seqEsperado = seqInicial;

            while (true) {
                try {
                    String msgrecibido = recibir(socket);

                    // EOF
                    if (msgrecibido.equals("EOF")) {
                        enviar(socket, "ACK:EOF", ipServidor, puertoTransferencia);
                        log(logCliente, "[CLIENTE] -> ACK:EOF enviado");
                        break;
                    }

                    String msgPlano = AESUtils.descifrar(msgrecibido, claveSesion);

                    // Datos
                    String[] partes = msgPlano.split(":", 2);
                    int seq = Integer.parseInt(partes[0]);
                    String linea = partes[1];

                    if (seq == seqEsperado) {
                        if (writer == null) {
                            writer = new BufferedWriter(
                                    new FileWriter("Copia_" + archivoSolicitado));
                            log(logCliente, "[CLIENTE] Archivo creado");
                        }
                        writer.write(linea);
                        writer.newLine();
                        seqEsperado++;
                        log(logCliente, "[CLIENTE] Línea escrita SEQ=" + seq);
                    }

                    // ACK en texto plano
                    enviar(socket, "ACK:" + seq, ipServidor, puertoTransferencia);
                    log(logCliente, "[CLIENTE] -> ACK enviado: " + seq);

                } catch (SocketTimeoutException e) {
                    log(logCliente, "[CLIENTE] Timeout esperando datos");
                } catch (Exception e) {
                    log(logCliente, "[CLIENTE] Paquete inválido o manipulado");
                }
            }

            if (writer != null) {
                writer.close();
            }

            // FOUR-WAY HANDSHAKE CIFRADO
            String finrecibido = recibir(socket);

            if (finrecibido.equals("FIN")) {
                enviar(socket, "ACK:FIN", ipServidor, puertoTransferencia);

                enviar(socket, "FIN", ipServidor, puertoTransferencia);

                String ackFinal = recibir(socket); // ACK:FIN 
                if (!ackFinal.equals("ACK:FIN")) {
                    log(logCliente, "[CLIENTE] ACK final inesperado: " + ackFinal);
                }

                log(logCliente, "[CLIENTE] Cierre de conexión completado");
            }

            log(logCliente, "[CLIENTE] Transferencia finalizada correctamente");

            logCliente.close();
            socket.close();

            System.out.println("Transferencia finalizada");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // Envío
    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {

        byte[] data = msg.getBytes();
        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);

        log(logCliente, "[CLIENTE] -> ENVIANDO: \"" + msg);

        socket.send(p);
    }

    // Recepcion    
    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);

        String msg = new String(p.getData(), 0, p.getLength()).trim();

        log(logCliente, "[CLIENTE] <- RECIBIDO: \"" + msg);

        return msg;
    }

    // Log
    private static synchronized void log(BufferedWriter log, String msg)
            throws IOException {
        String fechaHora = LocalDateTime.now().format(FORMATO_FECHA);
        log.write("[" + fechaHora + "] " + msg);
        log.newLine();
        log.flush();
    }
}