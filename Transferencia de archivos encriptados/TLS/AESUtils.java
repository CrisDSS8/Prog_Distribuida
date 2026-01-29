package TLS;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

public class AESUtils {

    private static final String TRANSFORMACION = "AES/GCM/NoPadding";
    private static final int GCM_TAG_LENGTH = 128; // bits
    private static final int GCM_IV_LENGTH = 12;   // bytes (recomendado)

    // 🔑 Clave de sesión (temporal)
    public static SecretKey generarClaveAES() throws Exception {
        KeyGenerator kg = KeyGenerator.getInstance("AES");
        kg.init(128); // AES-128
        return kg.generateKey();
    }

    // 🔐 Cifrar (devuelve Base64 listo para enviar)
    public static String cifrar(String data, SecretKey key) throws Exception {
        byte[] iv = new byte[GCM_IV_LENGTH];
        new SecureRandom().nextBytes(iv);

        Cipher cipher = Cipher.getInstance(TRANSFORMACION);
        GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
        cipher.init(Cipher.ENCRYPT_MODE, key, spec);

        byte[] cifrado = cipher.doFinal(data.getBytes());

        // IV || CIPHERTEXT
        byte[] combinado = new byte[iv.length + cifrado.length];
        System.arraycopy(iv, 0, combinado, 0, iv.length);
        System.arraycopy(cifrado, 0, combinado, iv.length, cifrado.length);

        return Base64.getEncoder().encodeToString(combinado);
    }

    // 🔓 Descifrar
    public static String descifrar(String data, SecretKey key) throws Exception {
        byte[] combinado = Base64.getDecoder().decode(data);

        byte[] iv = new byte[GCM_IV_LENGTH];
        byte[] cifrado = new byte[combinado.length - GCM_IV_LENGTH];

        System.arraycopy(combinado, 0, iv, 0, GCM_IV_LENGTH);
        System.arraycopy(combinado, GCM_IV_LENGTH, cifrado, 0, cifrado.length);

        Cipher cipher = Cipher.getInstance(TRANSFORMACION);
        GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
        cipher.init(Cipher.DECRYPT_MODE, key, spec);

        return new String(cipher.doFinal(cifrado));
    }

    // 🔁 Para enviar la clave en el handshake
    public static String claveToString(SecretKey key) {
        return Base64.getEncoder().encodeToString(key.getEncoded());
    }

    public static SecretKey stringToClave(String key) {
        byte[] decoded = Base64.getDecoder().decode(key);
        return new SecretKeySpec(decoded, "AES");
    }
}
