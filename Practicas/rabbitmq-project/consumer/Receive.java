import com.rabbitmq.client.*;

public class Receive {
    private final static String QUEUE_NAME = "hello";

    public static void main(String[] argv) throws Exception {
        // Esperar a que RabbitMQ esté listo
        ConnectionFactory factory = new ConnectionFactory();
        factory.setHost("rabbitmq");

        Connection connection = null;
        while (connection == null) {
            try {
                connection = factory.newConnection();
            } catch (Exception e) {
                System.out.println(" [!] RabbitMQ no disponible, reintentando en 3 segundos...");
                Thread.sleep(3000);
            }
        }

        Channel channel = connection.createChannel();
        channel.queueDeclare(QUEUE_NAME, false, false, false, null);

        System.out.println(" [*] Esperando mensajes...");

        DeliverCallback callback = (consumerTag, delivery) -> {
            String message = new String(delivery.getBody(), "UTF-8");
            System.out.println(" [x] Recibido: '" + message + "'");
        };

        channel.basicConsume(QUEUE_NAME, true, callback, consumerTag -> {});
    }
}