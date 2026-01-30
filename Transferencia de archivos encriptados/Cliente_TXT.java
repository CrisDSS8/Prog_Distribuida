import TLS.AESUtils;
import java.io.*;
import java.net.*;
import java.util.Scanner;
import javax.crypto.SecretKey;

public class Cliente_TXT {

    private static BufferedWriter writer = null;
    private static BufferedWriter logCliente;
    private static final int BUFFER = 1024;
    private static SecretKey claveSesion;

    public static void main(String[] args) {
        try {
            InetAddress ipServidor = InetAddress.getByName("172.31.11.137");
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
                log(logCliente, "[CLIENTE] Respuesta inesperada");
                socket.close();
                return;
            }

            int puertoTransferencia = Integer.parseInt(respuesta.split(":")[1]);

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
            int seqEsperado = 0;

            while (true) {
                try {
                    String msgCifrado = recibir(socket);
                    String msgPlano = AESUtils.descifrar(msgCifrado, claveSesion);

                    log(logCliente, "[CLIENTE] <- Descifrado: " + msgPlano);

                    // EOF
                    if (msgPlano.equals("EOF")) {
                        enviar(socket,
                                AESUtils.cifrar("ACK:EOF", claveSesion),
                                ipServidor, puertoTransferencia);

                        log(logCliente, "[CLIENTE] -> ACK:EOF enviado");
                        break;
                    }

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

                    // ACK cifrado
                    enviar(socket,
                            AESUtils.cifrar("ACK:" + seq, claveSesion),
                            ipServidor, puertoTransferencia);

                    log(logCliente, "[CLIENTE] -> ACK cifrado enviado: " + seq);

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
            String finCifrado = recibir(socket);
            String finPlano = AESUtils.descifrar(finCifrado, claveSesion);

            if (finPlano.equals("FIN")) {
                enviar(socket,
                        AESUtils.cifrar("ACK:FIN", claveSesion),
                        ipServidor, puertoTransferencia);

                enviar(socket,
                        AESUtils.cifrar("FIN", claveSesion),
                        ipServidor, puertoTransferencia);

                recibir(socket); // ACK:FIN cifrado
                log(logCliente, "[CLIENTE] Cierre de conexión cifrado completado");
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

        log(logCliente,
                "[CLIENTE] -> ENVIANDO: \"" + msg + "\" a "
                        + ip.getHostAddress() + ":" + puerto);

        socket.send(p);
    }

    // Recepcion    
    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);

        String msg = new String(p.getData(), 0, p.getLength()).trim();

        log(logCliente,
                "[CLIENTE] <- RECIBIDO: \"" + msg + "\" desde "
                        + p.getAddress().getHostAddress()
                        + ":" + p.getPort());

        return msg;
    }

    // Log
    private static synchronized void log(BufferedWriter log, String msg)
            throws IOException {
        log.write(msg);
        log.newLine();
        log.flush();
    }
}
