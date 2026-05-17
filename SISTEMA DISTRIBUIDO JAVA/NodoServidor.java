import comunicacion.ComunicacionUDP;
import directorio.Directorio;
import repositorio.Repositorio;
import sincronizacion.Sincronizador;
import TTL.TTLManager;
import log.LoggerNodo;

public class NodoServidor {

    public static void main(String[] args) throws Exception {

        int idNodo = Integer.parseInt(args[0]);
        int puerto = Integer.parseInt(args[1]);

        LoggerNodo logger = new LoggerNodo("log_nodo_" + idNodo + ".txt");

        Directorio directorio = new Directorio();
        Repositorio repositorio = new Repositorio(directorio, logger);

        Sincronizador sincronizador =
                new Sincronizador(idNodo, puerto, directorio, logger);

        TTLManager ttlManager = new TTLManager(directorio, logger);

        ComunicacionUDP servidor =
                new ComunicacionUDP(puerto, repositorio, logger);

        logger.log("Nodo " + idNodo + " iniciado en puerto " + puerto);

        new Thread(ttlManager).start();
        new Thread(sincronizador).start();

        servidor.iniciar();
    }
}