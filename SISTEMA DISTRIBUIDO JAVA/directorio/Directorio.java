package directorio;

import java.util.*;

public class Directorio {

    private Map<String, RegistroArchivo> archivos = new HashMap<>();

    public synchronized void agregar(RegistroArchivo r) {
        archivos.put(r.getNombre(), r);
    }

    public synchronized RegistroArchivo buscar(String nombre) {
        return archivos.get(nombre);
    }

    public synchronized void eliminar(String nombre) {
        archivos.remove(nombre);
    }

    public synchronized Collection<RegistroArchivo> listar() {
        return archivos.values();
    }
}