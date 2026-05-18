package directorio;

public class RegistroArchivo {

    private String nombre;
    private String duenio;
    private long size;
    private int ttl;

    public RegistroArchivo(String nombre,
                           String duenio,
                           long size,
                           int ttl) {

        this.nombre = nombre;
        this.duenio = duenio;
        this.size = size;
        this.ttl = ttl;
    }

    public String getNombre() { return nombre; }

    public int getTtl() { return ttl; }

    public void reducirTTL() { ttl--; }
}