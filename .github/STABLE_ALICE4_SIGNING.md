# Alice4 stable signing policy

Package: `com.bydmate.app.alice4`

All stable Alice4 builds intended to update an installed stable Alice4 APK must use the same persistent signing certificate. Do not use GitHub Actions' ephemeral debug key for distributable updates.

Current stable certificate SHA-256:
`B8:39:BC:11:CF:AD:61:EC:6A:89:DE:10:DC:0E:5E:B7:4C:BA:25:C5:7D:A1:16:AD:E3:0B:F4:A8:9D:70:C0:54`

Alias: `bydmate-alice`

The private keystore is intentionally NOT committed to the repository. CI reconstructs it only from protected GitHub Actions secrets and must verify this fingerprint before publishing an APK.

Each subsequent build must increment `versionCode` while preserving the package id and signer.
