package log;

import java.io.*;
import java.time.LocalDateTime;

public class LoggerNodo {

    private BufferedWriter writer;

    public LoggerNodo(String archivo) throws Exception {

        writer =
            new BufferedWriter(new FileWriter(archivo, true));
    }

    public synchronized void log(String msg) {

        try {

            writer.write(
                "[" + LocalDateTime.now() + "] " + msg);

            writer.newLine();
            writer.flush();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}