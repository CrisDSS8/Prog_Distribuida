import java.net.*;
import java.io.*;
import java.util.concurrent.*;

public class Servidor_TXT {
    private static final int PUERTO = 20000;

    public static void main(String[] args) {
        try {
            DatagramSocket socket = new DatagramSocket(PUERTO);
            System.out.println("Servidor iniciado en el puerto: " + PUERTO);

            ExecutorService pool = Executors.newCachedThreadPool(); 

            while (true) {
                byte[] buffer = new byte[1024];
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                socket.receive(packet);
                
                pool.execute((new AdministradorCliente(socket, packet)));
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}

class AdministradorCliente implements Runnable {

    private static final int TIMEOUT = 2000;
    private static final String RUTA_BASE = "C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Archivos compartidos/Textos txt/";

    private DatagramSocket socket;
    private InetAddress clienteIP;
    private int clientePuerto;

    AdministradorCliente(DatagramSocket socket, DatagramPacket packet) {
        this.socket = socket;
        this.clienteIP = packet.getAddress();
        this.clientePuerto = packet.getPort();
    }

    @Override
    public void run() {
        try {
            socket.setSoTimeout(TIMEOUT);

            //THREE-WAY HANDSHAKE
            enviar("SYN-ACK");
            esperar("ACK");

            String solicitud = recibir();
            String nombreArchivo = solicitud.split("\\|")[1];

            String ruta_completa = RUTA_BASE + nombreArchivo;
            File archivo = new File(ruta_completa);

            if (!archivo.exists()) {
                enviar("ERROR: " + archivo + " no encontrado");
                return;
            }

            //Funcion solicitada
            enviarArchivoTXT(socket.getLocalAddress(), clienteIP, clientePuerto, nombreArchivo);

            //FOUR-WAY HANDSHAKE
            esperar("FIN");
            enviar("ACK");
            enviar("FIN");
            esperar("ACK");

            System.out.println("Transferencia finalizada con " + clienteIP);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    //FUNCIONES  
    public void enviarArchivoTXT(InetAddress ipOrigen, InetAddress ipDestino, int puertoDestino, String nombreArchivo) throws IOException {
        BufferedReader reader = new BufferedReader(new FileReader(nombreArchivo));
        String linea;
        int SEQ = 0;

        while ((linea = reader.readLine()) != null) {
            boolean confirmado = false;

            while (!confirmado) {
                enviar("DATA|" + SEQ + "|" + linea);

                try {
                    String ack = recibir();
                    if (ack.equals("ACK|" + SEQ)) {
                        confirmado = true;
                    }
                } catch (SocketTimeoutException e) {
                    System.out.println("TIMEOUT... Reenviando SEQ " + SEQ);
                }
            }
            SEQ++;
        }
        reader.close();
    }

    private void enviar(String msj) throws IOException {
        byte[] datos = msj.getBytes();
        DatagramPacket packet = new DatagramPacket(datos, datos.length, clienteIP, clientePuerto);
        socket.send(packet);
    }

    private String recibir() throws IOException {
        byte[] buffer = new byte[1024];
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
        socket.receive(packet);
        return new String(packet.getData(), 0, packet.getLength());
    }

    private void esperar(String msjEsperado) throws IOException {
        while(true) {
            if (recibir().equals(msjEsperado)) break;
        }
    }
}