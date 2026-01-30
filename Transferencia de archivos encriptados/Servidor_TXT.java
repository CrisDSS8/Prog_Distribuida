import TLS.AESUtils;
import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import javax.crypto.SecretKey;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;


public class Servidor_TXT {

    //Declaración de variables globales

    private static final int PUERTO = 20000;
    private static final int BUFFER = 1024;
    private static final DateTimeFormatter FORMATO_FECHA = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static BufferedWriter logServidor;
    private static final String CARPETA ="C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Archivos compartidos/Textos txt/";
    private static final String RUTA_LOG = "C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Codigo/Transferencia de archivos encriptados/log_servidor.txt";
    private static ExecutorService pool = Executors.newCachedThreadPool();

    public static void main(String[] args) throws Exception {

        //Creacion del socket

        DatagramSocket socket = new DatagramSocket(PUERTO);

        logServidor = new BufferedWriter(new FileWriter(RUTA_LOG, true));
        System.out.println("\n----- Servidor de transferencia TXT (UDP)-----\n");
        System.out.println("Servidor iniciado correctamente");
        System.out.println("Puerto de escucha: " + PUERTO);
        System.out.println("Esperando clientes...");

        log(logServidor, "[SERVIDOR] Servidor iniciado correctamente en puerto " + PUERTO);
        log(logServidor, "[SERVIDOR] Esperando clientes...");

        //Detener el servidor segun se requiera

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                System.out.println("\nServidor Detenido.\n");
                log(logServidor, "[SERVIDOR] Servidor detenido");
                pool.shutdownNow();   
                socket.close();  
                logServidor.close();
            } catch (Exception ignored) {}
        }));

        //Cracion de hilos mediante pool para manejar los clientes de manera concurrente

        while (true) {
            byte[] buffer = new byte[BUFFER];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            socket.receive(packet);

            pool.execute(() -> manejarCliente(packet));
        }
    }

    private static void manejarCliente(DatagramPacket packet) {
        try {
            InetAddress ipCliente = packet.getAddress();
            int puertoCliente = packet.getPort();
            String archivo = new String(packet.getData(), 0, packet.getLength()).trim();

            DatagramSocket socketCliente = new DatagramSocket();
            socketCliente.setSoTimeout(3000);
            int puertoTransferencia = socketCliente.getLocalPort();

            System.out.println("\nNueva solicitud recibida desde " + ipCliente.getHostAddress() + ":" + puertoCliente);
            System.out.println("Archivo solicitado: " + archivo);
            log(logServidor, "[SERVIDOR] Nueva solicitud recibida desde " + ipCliente.getHostAddress() + ":" + puertoCliente);
            log(logServidor, "[SERVIDOR] Archivo solicitado: " + archivo);


            //THREE-WAY HANDSHAKE
            log(logServidor, "[SERVIDOR] -> SYN enviado (puerto " + puertoTransferencia + ")");
            enviar(socketCliente, "SYN:" + puertoTransferencia, ipCliente, puertoCliente);

            if (!esperar(socketCliente, "ACK")) {
                log(logServidor, "[SERVIDOR] <- ACK no recibido. Cancelando conexión");
                socketCliente.close();
                return;
            }

            log(logServidor, "[SERVIDOR] <- ACK recibido. Conexión establecida");

            System.out.println("Iniciando transferencia del archivo...");
            log(logServidor, "[SERVIDOR] Iniciando transferencia del archivo...");
            enviarArchivoUDP(socketCliente, ipCliente, puertoCliente, archivo, logServidor);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    //FUNCIÓN para enviar el archivo UDP pidiendo parametros socket, ipDestino, puertoDestino, archivo, log

    public static void enviarArchivoUDP(DatagramSocket socket, InetAddress ipDestino, int puertoDestino, String nombreArchivo, 
        BufferedWriter log) throws Exception {

        // ===== HANDSHAKE TLS =====
        SecretKey claveSesion = handshakeTLS(socket, ipDestino, puertoDestino, log);

        File archivo = new File(CARPETA + nombreArchivo);

        if (!archivo.exists()) {
            System.out.println("ERROR: archivo no existe");  
            log(logServidor, "[SERVIDOR] ERROR: archivo no existe");
            enviar(socket, "ERROR:ARCHIVO_NO_EXISTE", ipDestino, puertoDestino);
            cerrar(socket, ipDestino, puertoDestino, log);
            socket.close();
            return;
        }

        BufferedReader reader = new BufferedReader(new FileReader(archivo));
        String linea;
        int seq = 0;

        while ((linea = reader.readLine()) != null) {
            boolean ok = false;
            int intentos = 0;

            while (!ok && intentos < 5) {

                String msgPlano = seq + ":" + linea;
                String cifrado = AESUtils.cifrar(msgPlano, claveSesion);
                enviar(socket, cifrado, ipDestino, puertoDestino);
                log(logServidor, "[SERVIDOR] Enviado SEQ=" + seq + 
                    " (intento " + (intentos + 1) + ")");

                try {
                    String ackCifrado = recibir(socket);
                    String ackPlano = AESUtils.descifrar(ackCifrado, claveSesion);

                    log(logServidor, "[SERVIDOR] ACK recibido (descifrado): " + ackPlano);

                    if (ackPlano.equals("ACK:" + seq)) {
                        ok = true;
                        log(logServidor, "[SERVIDOR] SEQ=" + seq + " confirmado");
                    }

                } catch (IOException e) {
                    log(logServidor, "[SERVIDOR] Error al recibir ACK");
                } catch (Exception e) {
                    log(logServidor, "[SERVIDOR] ACK inválido o manipulado");
                }

                intentos++;
            }

            if (!ok) {
                log(logServidor, "[SERVIDOR] Cliente no responde. Abortando transferencia");
                reader.close();
                return;
            }
            seq++;
        }
        reader.close();

        log(logServidor, "[SERVIDOR] -> EOF enviado");
        enviar(socket, "EOF", ipDestino, puertoDestino);

        esperar(socket, "ACK:EOF");
        log(logServidor, "[SERVIDOR] <- ACK:EOF recibido");
        
        System.out.println("Archivo '" + nombreArchivo + ".txt' transferido correctamente");   
        System.out.println("Conexión finalizada con el cliente \n");
        log(logServidor, "[SERVIDOR] Archivo '" + nombreArchivo + ".txt' transferido correctamente");
        log(log, "[SERVIDOR] Conexión finalizada con el cliente \n");

        //FOUR-WAY HANDSHAKE
        cerrar(socket, ipDestino, puertoDestino ,log);

        socket.close();
    }

    //Funciones auxiliares

    private static void cerrar(DatagramSocket socket, InetAddress ipDestino, int puertoDestino, BufferedWriter log) throws Exception {
        log(logServidor, "[SERVIDOR] -> FIN enviado");
        enviar(socket, "FIN", ipDestino, puertoDestino);

        esperar(socket, "ACK:FIN");
        log(logServidor, "[SERVIDOR] <- ACK:FIN recibido");

        esperar(socket, "FIN");
        log(logServidor, "[SERVIDOR] <- FIN recibido");

        enviar(socket, "ACK:FIN", ipDestino, puertoDestino);
        log(logServidor, "[SERVIDOR] -> ACK:FIN enviado");
    }

    private static void enviar(DatagramSocket socket, String msg,
                               InetAddress ip, int puerto) throws Exception {
        byte[] data = msg.getBytes();
        socket.send(new DatagramPacket(data, data.length, ip, puerto));
    }

    private static boolean esperar(DatagramSocket socket, String esperado) throws Exception {
         try {
            byte[] buffer = new byte[BUFFER];
            DatagramPacket p = new DatagramPacket(buffer, buffer.length);
            socket.receive(p);

            String r = new String(p.getData(), 0, p.getLength()).trim();
            return r.equals(esperado);

        } catch (SocketTimeoutException e) {
            return false; 
        } catch (IOException e) {
            return false;
        }
    }

    public static String recibir(DatagramSocket socket) throws IOException {
        byte[] buffer = new byte[4096];
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
        socket.receive(packet);

        return new String(packet.getData(), 0, packet.getLength());
    }


    private static synchronized void log(BufferedWriter log, String msg) throws IOException {
        String fechaHora = LocalDateTime.now().format(FORMATO_FECHA);
        log.write("[" + fechaHora + "] " + msg);
        log.newLine();
        log.flush();
    }

    private static SecretKey handshakeTLS(DatagramSocket socket, InetAddress ip, int puerto, BufferedWriter log) throws Exception {

    SecretKey claveSesion = AESUtils.generarClaveAES();
    String claveBase64 = AESUtils.claveToString(claveSesion);

    enviar(socket, "TLS_KEY:" + claveBase64, ip, puerto);

    if (!esperar(socket, "TLS_ACK")) {
        throw new Exception("Handshake TLS fallido");
    }

    return claveSesion;
    }
}