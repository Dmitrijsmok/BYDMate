import java.io.File;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Base64;
import java.util.HexFormat;
import java.util.StringJoiner;

/** Read-only entry inventory for ci_release.py. Stdout is captured, never logged. */
class SigningKeyInventory {
    public static void main(String[] args) {
        char[] password = null;
        boolean failed = false;
        try {
            if (args.length != 1) {
                throw new IllegalArgumentException();
            }
            String secret = System.getenv("BYDMATE_KEYSTORE_PASSWORD");
            if (secret == null || secret.isEmpty()) {
                throw new IllegalArgumentException();
            }
            password = secret.toCharArray();
            // Auto-detect the existing JKS/PKCS12 format; never create or rewrite it.
            KeyStore store = KeyStore.getInstance(new File(args[0]), password);
            StringJoiner entries = new StringJoiner(",", "[", "]");
            var aliases = store.aliases();
            while (aliases.hasMoreElements()) {
                String alias = aliases.nextElement();
                String type = store.entryInstanceOf(alias, KeyStore.PrivateKeyEntry.class)
                        ? "private" : store.isCertificateEntry(alias) ? "trusted" : "other";
                var cert = store.getCertificate(alias);
                String digest = cert == null ? "" : HexFormat.of().withUpperCase().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(cert.getEncoded()));
                String encodedAlias = Base64.getEncoder().encodeToString(alias.getBytes(StandardCharsets.UTF_8));
                entries.add("{\"alias\":\"" + encodedAlias + "\",\"type\":\"" + type
                        + "\",\"sha256\":\"" + digest + "\"}");
            }
            // Only entry metadata and public certificate hashes; no key is accessed/exported.
            System.out.println(entries);
        } catch (Exception ignored) {
            System.err.println("Keystore inventory failed");
            failed = true;
        } finally {
            if (password != null) {
                Arrays.fill(password, '\0');
            }
        }
        if (failed) {
            System.exit(1);
        }
    }
}
