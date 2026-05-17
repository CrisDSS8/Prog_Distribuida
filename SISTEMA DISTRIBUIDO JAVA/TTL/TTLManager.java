package TTL;

import directorio.Directorio;
import directorio.RegistroArchivo;
import log.LoggerNodo;

public class TTLManager implements Runnable {

    private Directorio directorio;
    private LoggerNodo logger;

    public TTLManager(Directorio d, LoggerNodo logger) {
        this.directorio = d;
        this.logger = logger;
    }

    @Override
    public void run() {

        while (true) {

            try {

                Thread.sleep(5000);

                for (RegistroArchivo r :
                        directorio.listar()) {

                    r.reducirTTL();

                    if (r.getTtl() <= 0) {
                        directorio.eliminar(r.getNombre());
                        logger.log("Registro expirado: "
                                + r.getNombre());
                    }
                }

            } catch (Exception e) {
                logger.log("Error TTLManager");
            }
        }
    }
}