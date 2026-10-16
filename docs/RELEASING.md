# DiLink3 fork APK filenames

The APK filename convention is **`BYDMate-dilink3-vX.Y.Z.apk`**, using the
existing Gradle `versionName`. Examples: `BYDMate-dilink3-v1.0.0.apk` and
`BYDMate-dilink3-v1.0.1.apk`.

Both build types use the same filename in separate directories:

- Debug: `app/build/outputs/apk/debug/BYDMate-dilink3-vX.Y.Z.apk`
- Release: `app/build/outputs/apk/release/BYDMate-dilink3-vX.Y.Z.apk`

Build a debug APK with `./gradlew :app:assembleDebug`. A release build requires
the existing owner-controlled signing configuration; do not generate replacement
keys or bypass signing checks. The filename does not identify the signing type.

## OTA and release preparation

The OTA source remains
[`Dmitrijsmok/BYDMate` latest release](https://api.github.com/repos/Dmitrijsmok/BYDMate/releases/latest).
For a release tagged `vX.Y.Z`, the updater selects exactly
`BYDMate-dilink3-vX.Y.Z.apk` from that fork. The download destination and installer
both use `Download/BYDMate-dilink3-vX.Y.Z.apk`.

`scripts/prepare-release.sh X.Y.Z` reads the release APK at the path above when
printing its SHA-256. The script also edits `CHANGELOG.md`; run it only when
actually preparing an approved release, not just to inspect an APK filename.
Publishing still requires explicit owner approval.

Cleanup recognizes the new `BYDMate-dilink3-` prefix and otherwise retains its
existing numeric-version comparison and optional-`v` handling. Current/newer
APKs, malformed names, directories, original `BYDMate-` APKs, and old
`DiLink3Friendly-` APKs are left untouched.

Older installed builds that only recognize `DiLink3Friendly-vX.Y.Z.apk` cannot
discover the renamed asset through their old matcher. A manual upgrade using
the same application ID and signing identity may be needed for that transition.

This filename migration does not change application ID `com.bydmate.dilink3.app`,
Kotlin namespace `com.bydmate.app`, versions, signing identity, or assistant behavior.

## Automatic permanent signing on main

The existing `.github/workflows/ci.yml` runs the release-verifier regression tests,
Android unit tests, Android Lint, and Detekt on both PRs and pushes to `main`.
After those checks pass, a separate, fresh runner builds a signed **release** APK
with `:app:assembleRelease`. Signing runs only for `push` events on
`Dmitrijsmok/BYDMate`'s `main`, never for PR code. Each main push has its own run;
new pushes do not cancel older main builds.

The workflow reuses the three existing historical Alice GitHub Actions repository
secrets. No new `BYDMATE_*` repository secrets or alias secret are required; those
environment names are internal mappings only. Never generate a replacement key:

| Existing repository secret | Internal step environment | Value |
| --- | --- | --- |
| `ALICE_SIGNING_KEYSTORE_B64` | `BYDMATE_KEYSTORE_BASE64` | Base64-encoded existing keystore |
| `ALICE_SIGNING_STORE_PASSWORD` | `BYDMATE_KEYSTORE_PASSWORD` | Keystore password |
| `ALICE_SIGNING_KEY_PASSWORD` | `BYDMATE_KEY_PASSWORD` | Private-key entry password |

Secret names are inspectable, but GitHub does not return their stored values.
Missing secrets, an invalid keystore/password, missing or ambiguous matching aliases,
or a mismatched certificate must fail the signing job. Existing secret names alone
do not prove their contents: actual restoration and signing can only be confirmed
by a successful authorized Actions run.

The permanent BYDMate Alice signing certificate is pinned in `scripts/ci_release.py`:

```text
B8:39:BC:11:CF:AD:61:EC:6A:89:DE:10:DC:0E:5E:B7:4C:BA:25:C5:7D:A1:16:AD:E3:0B:F4:A8:9D:70:C0:54
```

Before building, `scripts/SigningKeyInventory.java` uses Java 17's read-only KeyStore
API to inventory entry types and leaf certificate hashes, avoiding localized
`keytool` listing parsing. The Python script accepts **exactly one private-key entry**
whose certificate matches the pin. Trusted-certificate-only entries cannot qualify;
zero or multiple matching private-key entries fail closed, even if aliases contain
the same certificate. No alias is guessed, supplied by a secret, or logged.
The script then independently hashes the selected DER certificate exported by
`keytool` and compares it to the pin. It probes private-key access using an in-memory CSR;
this does not generate a key or change the signing identity. After building,
`apksigner` independently verifies the APK signature and signer fingerprint.
`aapt` verifies the package, versions, and absence of debug/test-only flags.
Gradle output metadata must identify a release APK with the exact filename and
versions declared in `app/build.gradle.kts`.

Only the verified APK and public `verification.json` are uploaded, for 30 days,
as `BYDMate-dilink3-release-<commit SHA>-<run number>-<attempt>`. The APK inside
retains `BYDMate-dilink3-vX.Y.Z.apk`. The JSON records its SHA-256, certificate
fingerprint, package, versions, release variant, and source commit.

### Security boundaries for review

- The workflow token has `contents: read`; no step creates tags or GitHub Releases.
- Checkout does not persist credentials. PR/check runners receive no signing secrets.
- Secrets are scoped to one signing step on a fresh GitHub-hosted runner. Signing
  caches, Gradle configuration/build caches, and long-lived Gradle daemons are disabled.
- Keystore and properties files have mode `0600`; the keystore lives in a private
  temporary directory outside the checkout. Controlled success/failure paths remove
  both files before artifact staging. A forcibly terminated run relies on disposal
  of the ephemeral runner; secrets are never included in artifact paths or caches.
- The inventory helper and `keytool` read passwords through environment references,
  not command-line values. Inventory output and the CSR are captured, never logged.
  The script never forwards raw signing/build subprocess output or exception details
  that could disclose credentials. Failures therefore provide deliberately limited logs.
- Main's code/build scripts can execute with access to signing material. Protect main
  and review workflow/build-script changes; masking alone is not a security boundary.
  Do not enable shell tracing, upload the workspace, add `pull_request_target`, or
  move signing to an untrusted/self-hosted runner without a separate security review.
- Do not change the certificate pin to make a failed build pass. Investigate the
  configured secrets and recover the existing owner identity instead.

## Explicitly approved release procedure

1. Choose `X.Y.Z`, update `versionName`, and **increment `versionCode` above every
   previously published OTA release**. Keep the application ID and signing identity.
   Intermediate CI artifacts may share a code; two published OTA releases must not.
2. Review and approve the diff and security implications before committing/pushing
   to `main`. Wait for both CI jobs to pass; a filename or artifact title alone is
   not evidence of a valid release signature.
3. Download the artifact for the exact tested commit. Check `verification.json`
   against that commit, the expected versions, certificate pin, and APK SHA-256.
   From the same source revision, independently reverify the downloaded APK:

   ```sh
   python3 scripts/ci_release.py verify \
     --apk /path/to/BYDMate-dilink3-vX.Y.Z.apk \
     --build-tools "$ANDROID_HOME/build-tools/34.0.0"
   ```

4. Test installation/upgrade and vehicle behavior with this exact APK. Existing
   installations must use the same signing certificate; keep the test results.
5. Obtain explicit owner approval to publish. Create/push tag `vX.Y.Z` at the
   **artifact's tested commit**, not a newer main commit. Prepare approved notes
   including the APK SHA-256; `scripts/prepare-release.sh X.Y.Z` is optional and
   edits the changelog, so review any resulting changes separately.
6. Only after approval, publish a normal (not prerelease) GitHub Release in
   `Dmitrijsmok/BYDMate`, tagged `vX.Y.Z`, with the exact matching APK asset name.
   For an already approved and pushed tag, the manual CLI equivalent is:

   ```sh
   gh release create vX.Y.Z /path/to/BYDMate-dilink3-vX.Y.Z.apk \
     --repo Dmitrijsmok/BYDMate --verify-tag \
     --title "BYDMate DiLink3 X.Y.Z" --notes-file approved-release-notes.md
   ```

   Confirm it is the intended latest release for the unchanged OTA endpoint.
   **CI artifact upload is not release publication.** Never publish an unsigned or
   debug-signed APK, and never replace an existing release's asset with a differently
   signed build. All future release APKs must retain the pinned certificate.

Tool references: [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets),
[Java KeyStore API](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/security/KeyStore.html),
[Android APK signature verification](https://developer.android.com/tools/apksigner).
