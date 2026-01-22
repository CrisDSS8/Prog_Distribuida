import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;


public class Servidor_TXT {

    private static final int PUERTO = 20000;
    private static final int BUFFER = 1024;
    private static final DateTimeFormatter FORMATO_FECHA = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static BufferedWriter logServidor;
    private static final String CARPETA ="C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Archivos compartidos/Textos txt/";
    private static final String RUTA_LOG = "C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Codigo/Transferencia de archivos/log_servidor.txt";
    private static ExecutorService pool = Executors.newCachedThreadPool();

    public static void main(String[] args) throws Exception {

        DatagramSocket socket = new DatagramSocket(PUERTO);

        logServidor = new BufferedWriter(new FileWriter(RUTA_LOG, true));
        System.out.println("\n----- Servidor de transferencia TXT (UDP)-----\n");
        System.out.println("Servidor iniciado correctamente");
        System.out.println("Puerto de escucha: " + PUERTO);
        System.out.println("Esperando clientes...");

        log(logServidor, "[SERVIDOR] Servidor iniciado correctamente en puerto " + PUERTO);
        log(logServidor, "[SERVIDOR] Esperando clientes...");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                System.out.println("\nServidor Detenido.\n");
                log(logServidor, "[SERVIDOR] Servidor detenido");
                pool.shutdownNow();   
                socket.close();  
                logServidor.close();
            } catch (Exception ignored) {}
        }));

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

    public static void enviarArchivoUDP(DatagramSocket socket, InetAddress ipDestino, int puertoDestino, String nombreArchivo, 
        BufferedWriter log) throws Exception {

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
            while (!ok) {
                log(logServidor, "[SERVIDOR] -> SEQ=" + seq + " | " + linea);
                enviar(socket, seq + ":" + linea, ipDestino, puertoDestino);

                log(logServidor, "[SERVIDOR] <- Esperando ACK:" + seq);
                ok = esperar(socket, "ACK:" + seq);

                if (ok) {
                    log(logServidor, "[SERVIDOR] <- ACK:" + seq + " recibido");
                }
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
        byte[] buffer = new byte[BUFFER];
        DatagramPacket p = new DatagramPacket(buffer, buffer.length);
        socket.receive(p);
        String r = new String(p.getData(), 0, p.getLength()).trim();
        return r.equals(esperado);
    }

    private static synchronized void log(BufferedWriter log, String msg) throws IOException {
        String fechaHora = LocalDateTime.now().format(FORMATO_FECHA);
        log.write("[" + fechaHora + "] " + msg);
        log.newLine();
        log.flush();
    }
}