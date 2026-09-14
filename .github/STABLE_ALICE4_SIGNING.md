# Alice4 stable signing policy

Package: `com.bydmate.app.alice4`

All stable Alice4 builds intended to update an installed stable Alice4 APK must use the same persistent signing certificate. Do not use GitHub Actions' ephemeral debug key for distributable updates.

Current stable certificate SHA-256:
`F5:52:99:4D:7A:39:CD:B8:A0:1D:5F:93:16:C6:F9:D0:7C:8E:22:78:33:48:2C:2D:40:F2:C5:83:25:4B:E4:0D`

The private keystore is intentionally NOT committed to the repository.

Each subsequent build must increment `versionCode` while preserving the package id and signer.
