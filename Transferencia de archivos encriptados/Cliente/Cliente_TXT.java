import java.io.*;
import java.net.*;
import java.util.Scanner;

public class Cliente_TXT {
    private static BufferedWriter writer = null;
    private static BufferedWriter logCliente;
    private static final int BUFFER = 1024;

    public static void main(String[] args) {
        try {
            InetAddress ipServidor = InetAddress.getByName("172.31.8.176");
            int puertoServidor = 20000;

            DatagramSocket socket = new DatagramSocket();
            System.out.println("Cliente iniciado");

            logCliente = new BufferedWriter(new FileWriter("log_cliente.txt", true));
            log(logCliente, "[CLIENTE] Cliente iniciado");

            // nombre del archivo a solicitar
            Scanner sc = new Scanner(System.in);
            System.out.print("¿Qué archivo desea?: ");
            String archivoSolicitado = sc.nextLine();

            if (!archivoSolicitado.endsWith(".txt")) {
                archivoSolicitado += ".txt";
            }

            enviar(socket, archivoSolicitado, ipServidor, puertoServidor);
            //System.out.println("Archivo solicitado: " + archivoSolicitado);
            log(logCliente, "[CLIENTE] Archivo solicitado: " + archivoSolicitado);

            // espera SYN
            String respuesta = recibir(socket);
            if (!respuesta.startsWith("SYN:")) {
                //System.out.println("Respuesta inesperada: " + respuesta);
                log(logCliente, "[CLIENTE] Respuesta inesperada: " + respuesta);
                socket.close();
                return;
            }

            int puertoTransferencia =
                    Integer.parseInt(respuesta.split(":")[1]);

            System.out.println("Puerto de transferencia recibido: " + puertoTransferencia);
            log(logCliente, "[CLIENTE] Puerto de transferencia recibido: " + puertoTransferencia);

            // ACK al puerto de transferencia
            enviar(socket, "ACK", ipServidor, puertoTransferencia);
            log(logCliente, "[CLIENTE] <- SYN recibido: " + respuesta);
            log(logCliente, "[CLIENTE] -> ACK enviado");

            /*BufferedWriter writer =
                    new BufferedWriter(new FileWriter("copia_" + archivoSolicitado));*/

            // recibir
            int seqEsperado = 0;

            // archivo 
            while (true) {
                String msg = recibir(socket);

                if (msg.equals("EOF")) {
                    enviar(socket, "ACK:EOF", ipServidor, puertoTransferencia);
                    log(logCliente, "[CLIENTE] <- EOF recibido");
                    log(logCliente, "[CLIENTE] -> ACK:EOF enviado");
                    break;
                }

                if (msg.startsWith("ERROR")) {
                    //System.out.println("[CLIENTE] " + msg);
                    log(logCliente, "[CLIENTE] " + msg);
                    // Esperar FIN del servidor
                    String fin = recibir(socket);
                    if (fin.equals("FIN")) {
                        //System.out.println("[CLIENTE] <- FIN recibido");
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

                //System.out.println("[CLIENTE] Recibido SEQ " + seq);
                log(logCliente, "[CLIENTE] Recibido SEQ " + seq);

                if (seq == seqEsperado) {
                    if (writer == null) {
                        writer = new BufferedWriter(new FileWriter("Copia_" + archivoSolicitado));
                        //System.out.println("[CLIENTE] Archivo creado: " + archivoSolicitado);
                        log(logCliente, "[CLIENTE] Archivo creado: " + archivoSolicitado);
                    }
                    //System.out.println("[CLIENTE] -> Linea aceptada " + partes[0] + ":" + linea);
                    log(logCliente, "[CLIENTE] -> Línea aceptada: " + partes[0] + ":" + linea);
                    writer.write(linea);
                    writer.newLine();
                    seqEsperado++;
                } else {
                    System.out.println("[CLIENTE] -> SEQ duplicado descartado: ");
                    log(logCliente, "[CLIENTE] -> SEQ duplicado descartado: " + seq);
                }

                //ack
                enviar(socket, "ACK:" + seq, ipServidor, puertoTransferencia);
            }

            //writer.close();

            if (writer != null) {
                writer.close();
            }

            // FOUR WAY HANDSHAKE
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

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);

        /*System.out.println("[CLIENTE] -> ENVIANDO: \"" + msg +
                       "\" a " + ip.getHostAddress() + ":" + puerto);*/

        log(logCliente, "[CLIENTE] -> ENVIANDO: \"" + msg +
            "\" a " + ip.getHostAddress() + ":" + puerto);

        socket.send(p);
    }

    private static String recibir(DatagramSocket socket) throws Exception {
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);

        String msg = new String(p.getData(), 0, p.getLength()).trim();

        /*System.out.println("[CLIENTE] <- RECIBIDO: \"" + msg +
                        "\" desde " + p.getAddress().getHostAddress() +
                        ":" + p.getPort());*/

        log(logCliente, "[CLIENTE] <- RECIBIDO: \"" + msg +
            "\" desde " + p.getAddress().getHostAddress() +
            ":" + p.getPort());


        return msg;
    }

    private static synchronized void log(BufferedWriter log, String msg) throws IOException {
        log.write(msg);
        log.newLine();
        log.flush();
    }
}