package archivos;

import java.io.*;
import java.util.*;

public class AccesoArchivos {

    public static List<String> leer(String nombre) throws Exception {

        List<String> lineas = new ArrayList<>();

        BufferedReader br =
                new BufferedReader(new FileReader(nombre));

        String l;

        while ((l = br.readLine()) != null)
            lineas.add(l);

        br.close();

        return lineas;
    }

    public static void escribir(String nombre,
                                List<String> contenido) throws Exception {

        BufferedWriter bw =
                new BufferedWriter(new FileWriter(nombre));

        for (String l : contenido) {
            bw.write(l);
            bw.newLine();
        }

        bw.close();
    }
}