import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class Servidor {

    private static final String RUTA_CARPETA =
        "C:/Users/Cristopher Damian/Documents/Cristopher/BUAP (Benemerita Universidad Autonoma de Puebla)/7mo Semestre/Programacion distribuida aplicada/Archivos compartidos";

    public static void main(String[] args) {
        try {
            DatagramSocket socket = new DatagramSocket(20000);
            System.out.println("Servidor UDP escuchando en el puerto 20000...\n");

            List<String> mensajesRecibidos = new ArrayList<>();
            int vecesListaEnviada = 0;

            String listaArchivos = leerContenidoCarpeta(RUTA_CARPETA);

            boolean activo = true;

            while (activo) {
                byte[] buffer = new byte[1024];
                DatagramPacket paquete = new DatagramPacket(buffer, buffer.length);
                socket.receive(paquete);

                String mensaje = new String(
                        paquete.getData(),
                        0,
                        paquete.getLength(),
                        java.nio.charset.StandardCharsets.UTF_8
                ).trim();

                InetAddress ipCliente = paquete.getAddress();
                int puertoCliente = paquete.getPort();

                mensajesRecibidos.add(mensaje);

                System.out.println("Mensaje recibido de "
                        + ipCliente.getHostAddress() + ":" + puertoCliente
                        + " -> " + mensaje);

                if (mensaje.equalsIgnoreCase("salir")) {
                    System.out.println("\nComando salir recibido. Cerrando servidor...");
                    activo = false;
                    break;
                }

                if (mensaje.equalsIgnoreCase("LIST")) {
                    vecesListaEnviada++;

                    byte[] datos = listaArchivos.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    DatagramPacket respuesta = new DatagramPacket(
                            datos,
                            datos.length,
                            ipCliente,
                            puertoCliente
                    );

                    socket.send(respuesta);
                    System.out.println(">> Lista enviada al cliente");
                }

                System.out.println("Total de mensajes recibidos: " + mensajesRecibidos.size());
                System.out.println("Veces que se envió la lista: " + vecesListaEnviada);
                System.out.println("----------------------------------\n");
            }

            socket.close();

            System.out.println("Servidor UDP cerrado correctamente.");
            System.out.println("Mensajes recibidos en total: " + mensajesRecibidos.size());
            System.out.println("Listas enviadas en total: " + vecesListaEnviada);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    //Lectura de carpeta
    private static String leerContenidoCarpeta(String ruta) {
        File carpeta = new File(ruta);
        StringBuilder lista = new StringBuilder();

        if (carpeta.exists() && carpeta.isDirectory()) {
            File[] archivos = carpeta.listFiles();
            if (archivos != null) {
                for (File archivo : archivos) {
                    lista.append(archivo.getName()).append("\n");
                }
            }
        } else {
            lista.append("Error: la carpeta no existe");
        }

        return lista.toString();
    }
}
