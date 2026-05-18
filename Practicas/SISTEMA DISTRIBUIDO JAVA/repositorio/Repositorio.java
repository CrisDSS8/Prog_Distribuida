package repositorio;

import TLS.AESUtils;
import archivos.AccesoArchivos;
import directorio.Directorio;
import java.net.*;
import java.util.List;
import javax.crypto.SecretKey;
import log.LoggerNodo;

public class Repositorio {

    private Directorio directorio;
    private LoggerNodo logger;

    public Repositorio(Directorio d, LoggerNodo logger) {
        this.directorio = d;
        this.logger = logger;
    }

    public void enviarArchivo(String nombre,
                              DatagramSocket socket,
                              InetAddress ip,
                              int puerto,
                              SecretKey clave,
                              int seqInicial) throws Exception {

        List<String> lineas =
                AccesoArchivos.leer(nombre);

        int seq = seqInicial;

        for (String l : lineas) {

            String plano = seq + ":" + l;

            String cifrado =
                    AESUtils.cifrar(plano, clave);

            enviar(socket, cifrado, ip, puerto);

            seq++;
        }

        enviar(socket, "EOF", ip, puerto);

        enviar(socket, "FIN", ip, puerto);

        logger.log("Archivo enviado: " + nombre);
    }

    private void enviar(DatagramSocket s,
                        String msg,
                        InetAddress ip,
                        int puerto) throws Exception {

        byte[] data = msg.getBytes();

        DatagramPacket p =
                new DatagramPacket(data, data.length, ip, puerto);

        s.send(p);
    }
}