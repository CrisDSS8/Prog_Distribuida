package sincronizacion;

import directorio.Directorio;
import log.LoggerNodo;

public class Sincronizador implements Runnable {

    private int idNodo;
    private int puerto;
    private Directorio directorio;
    private LoggerNodo logger;

    public Sincronizador(int idNodo,
                         int puerto,
                         Directorio d,
                         LoggerNodo logger) {

        this.idNodo = idNodo;
        this.puerto = puerto;
        this.directorio = d;
        this.logger = logger;
    }

    @Override
    public void run() {

        while (true) {

            try {

                Thread.sleep(10000);

                logger.log("Sincronización periódica");

            } catch (Exception e) {
                logger.log("Error sincronizador");
            }
        }
    }
}