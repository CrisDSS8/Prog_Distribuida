import org.apache.xmlrpc.client.XmlRpcClient;
import org.apache.xmlrpc.client.XmlRpcClientConfigImpl;

import java.net.URL;
import java.util.Vector;

public class ConsumidorRPC {

    public static void main(String[] args) {

        try {

            XmlRpcClientConfigImpl config = new XmlRpcClientConfigImpl();
            config.setServerURL(new URL("http://localhost:8000"));

            XmlRpcClient client = new XmlRpcClient();
            client.setConfig(config);

            while(true){

                Object[] params = {};

                Object response = client.execute("obtener_vector", params);

                Object[] vector = (Object[]) response;

                if(vector.length == 0){
                    Thread.sleep(500);
                    continue;
                }

                int a = (int) vector[0];
                int b = (int) vector[1];
                int c = (int) vector[2];

                int resultado = a + b + c;

                Vector<Object> paramResultado = new Vector<>();
                paramResultado.add(resultado);

                client.execute("guardar_resultado", paramResultado);

                System.out.println("Resultado enviado: " + resultado);
            }

        } catch(Exception e){
            e.printStackTrace();
        }
    }
}