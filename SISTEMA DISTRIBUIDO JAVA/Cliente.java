import TLS.AESUtils;
import java.io.*;
import java.net.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Scanner;
import javax.crypto.SecretKey;

public class Cliente {

    private static final int BUFFER = 4096;
    private static final DateTimeFormatter FORMATO = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private static BufferedWriter logCliente;
    private static SecretKey claveSesion;

    private static InetAddress ipServidor;
    private static int puertoServidor;

    private static DatagramSocket socket;

    public static void main(String[] args) {

        try {

            ipServidor = InetAddress.getByName("192.168.1.73");
            puertoServidor = 20000;

            socket = new DatagramSocket();
            socket.setSoTimeout(4000);

            logCliente = new BufferedWriter(
                    new FileWriter("log_cliente.txt", true));

            log("[CLIENTE] Cliente distribuido iniciado");

            Scanner sc = new Scanner(System.in);

            while (true) {

                System.out.println("\n===== CLIENTE DISTRIBUIDO =====");
                System.out.println("1. Ver directorio distribuido");
                System.out.println("2. Buscar archivo");
                System.out.println("3. Usar / Editar archivo");
                System.out.println("4. Salir");
                System.out.print("Seleccione: ");

                int op = sc.nextInt();
                sc.nextLine();

                switch (op) {
                    case 1 -> solicitarLista();
                    case 2 -> buscarArchivo(sc);
                    case 3 -> usarArchivo(sc);
                    case 4 -> {
                        log("[CLIENTE] Cliente finalizado");
                        socket.close();
                        logCliente.close();
                        return;
                    }
                }
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ===============================
    // SOLICITAR LISTA
    // ===============================

    private static void solicitarLista() throws Exception {

        enviar("LIST");

        String respuesta = recibir();

        System.out.println("\n--- DIRECTORIO ---");
        System.out.println(respuesta);

        log("[CLIENTE] Lista solicitada");
    }

    // ===============================
    // BUSCAR ARCHIVO
    // ===============================

    private static void buscarArchivo(Scanner sc) throws Exception {

        System.out.print("Nombre archivo: ");
        String nombre = sc.nextLine();

        enviar("SEARCH:" + nombre);

        String resp = recibir();

        System.out.println("Respuesta: " + resp);

        log("[CLIENTE] Busqueda archivo: " + nombre);
    }

    // ===============================
    // USAR ARCHIVO
    // ===============================

    private static void usarArchivo(Scanner sc) throws Exception {

        System.out.print("Archivo a usar: ");
        String archivo = sc.nextLine();

        enviar("USE:" + archivo);

        String respuesta = recibir();

        if (!respuesta.startsWith("OK")) {
            System.out.println("No disponible");
            return;
        }

        log("[CLIENTE] Usando archivo " + archivo);

        recibirArchivoTLS(archivo);

        editarArchivoLocal(archivo);

        enviarArchivoModificado(archivo);

        new File("Copia_" + archivo).delete();

        log("[CLIENTE] Copia local eliminada");
    }

    // ===============================
    // HANDSHAKE + RECEPCION
    // ===============================

    private static void recibirArchivoTLS(String archivo) throws Exception {

        String syn = recibir();

        String[] partes = syn.split(":");

        int puertoTransfer = Integer.parseInt(partes[1]);
        int seq = Integer.parseInt(partes[2]);

        enviar("ACK", ipServidor, puertoTransfer);

        String tlsMsg = recibir();

        String claveBase64 = tlsMsg.substring(8);
        claveSesion = AESUtils.stringToClave(claveBase64);

        enviar("TLS_ACK", ipServidor, puertoTransfer);

        BufferedWriter writer = new BufferedWriter(
                new FileWriter("Copia_" + archivo));

        int esperado = seq;

        while (true) {

            String msg = recibir();

            if (msg.equals("EOF")) {
                enviar("ACK:EOF", ipServidor, puertoTransfer);
                break;
            }

            String plano = AESUtils.descifrar(msg, claveSesion);

            String[] p = plano.split(":", 2);

            int s = Integer.parseInt(p[0]);

            if (s == esperado) {
                writer.write(p[1]);
                writer.newLine();
                esperado++;
            }

            enviar("ACK:" + s, ipServidor, puertoTransfer);
        }

        writer.close();

        cerrarConexion(puertoTransfer);

        System.out.println("Archivo recibido");
    }

    // ===============================
    // EDITOR SIMPLE
    // ===============================

    private static void editarArchivoLocal(String archivo) throws Exception {

        File file = new File("Copia_" + archivo);

        System.out.println("\n--- CONTENIDO ---");

        BufferedReader br = new BufferedReader(new FileReader(file));
        br.lines().forEach(System.out::println);
        br.close();

        System.out.println("\nEscriba nuevo contenido (FIN para terminar):");

        BufferedWriter bw = new BufferedWriter(new FileWriter(file));

        Scanner sc = new Scanner(System.in);

        while (true) {
            String linea = sc.nextLine();
            if (linea.equals("FIN")) break;
            bw.write(linea);
            bw.newLine();
        }

        bw.close();

        log("[CLIENTE] Archivo editado");
    }

    // ===============================
    // ENVIAR MODIFICACIONES
    // ===============================

    private static void enviarArchivoModificado(String archivo) throws Exception {

        enviar("SAVE:" + archivo);

        log("[CLIENTE] Enviando modificaciones");

        // reutiliza transferencia anterior
    }

    // ===============================
    // CIERRE
    // ===============================

    private static void cerrarConexion(int puerto) throws Exception {

        String fin = recibir();

        if (fin.equals("FIN")) {

            enviar("ACK:FIN", ipServidor, puerto);
            enviar("FIN", ipServidor, puerto);

            recibir();
        }
    }

    // ===============================
    // RED
    // ===============================

    private static void enviar(String msg) throws Exception {
        enviar(msg, ipServidor, puertoServidor);
    }

    private static void enviar(String msg, InetAddress ip, int puerto) throws Exception {

        byte[] data = msg.getBytes();

        DatagramPacket p = new DatagramPacket(data, data.length, ip, puerto);

        socket.send(p);

        log("[CLIENTE] -> " + msg);
    }

    private static String recibir() throws Exception {

        byte[] buffer = new byte[BUFFER];

        DatagramPacket p = new DatagramPacket(buffer, buffer.length);

        socket.receive(p);

        String msg = new String(p.getData(), 0, p.getLength()).trim();

        log("[CLIENTE] <- " + msg);

        return msg;
    }

    // ===============================
    // LOG
    // ===============================

    private static synchronized void log(String msg) throws IOException {

        String fecha = LocalDateTime.now().format(FORMATO);

        logCliente.write("[" + fecha + "] " + msg);

        logCliente.newLine();

        logCliente.flush();
    }
}