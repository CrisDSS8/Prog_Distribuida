package comunicacion;

import TLS.AESUtils;
import java.net.*;
import java.util.Base64;
import javax.crypto.SecretKey;
import log.LoggerNodo;
import repositorio.Repositorio;

public class ComunicacionUDP {

    private DatagramSocket socket;
    private Repositorio repositorio;
    private LoggerNodo logger;

    private static final int BUFFER = 2048;

    public ComunicacionUDP(int puerto,
                           Repositorio repositorio,
                           LoggerNodo logger) throws Exception {

        socket = new DatagramSocket(puerto);
        this.repositorio = repositorio;
        this.logger = logger;
    }

    public void iniciar() throws Exception {

        byte[] buffer = new byte[BUFFER];

        while (true) {

            DatagramPacket packet =
                    new DatagramPacket(buffer, buffer.length);

            socket.receive(packet);

            String mensaje =
                    new String(packet.getData(), 0, packet.getLength());

            InetAddress ip = packet.getAddress();
            int puerto = packet.getPort();

            logger.log("REQUEST: " + mensaje);

            new Thread(() ->
                    manejarCliente(mensaje, ip, puerto)).start();
        }
    }

    private void manejarCliente(String archivo,
                                InetAddress ip,
                                int puertoCliente) {

        try {

            int puertoTransferencia =
                    30000 + (int)(Math.random() * 10000);

            int seqInicial = 1;

            enviar("SYN:" + puertoTransferencia + ":" + seqInicial,
                    ip, puertoCliente);

            DatagramSocket transferencia =
                    new DatagramSocket(puertoTransferencia);

            recibir(transferencia); // ACK

            SecretKey clave = AESUtils.generarClaveAES();

            String claveBase64 =
                    Base64.getEncoder().encodeToString(clave.getEncoded());

            enviar("TLS_KEY:" + claveBase64, ip, puertoCliente);

            recibir(transferencia); // TLS_ACK

            repositorio.enviarArchivo(
                    archivo, transferencia, ip,
                    puertoCliente, clave, seqInicial);

            transferencia.close();

        } catch (Exception e) {
            logger.log("ERROR: " + e.getMessage());
        }
    }

    private void enviar(String msg,
                        InetAddress ip,
                        int puerto) throws Exception {

        byte[] data = msg.getBytes();

        DatagramPacket p =
                new DatagramPacket(data, data.length, ip, puerto);

        socket.send(p);
    }

    private String recibir(DatagramSocket s) throws Exception {

        byte[] buffer = new byte[BUFFER];

        DatagramPacket p =
                new DatagramPacket(buffer, buffer.length);

        s.receive(p);

        return new String(p.getData(), 0, p.getLength());
    }
}