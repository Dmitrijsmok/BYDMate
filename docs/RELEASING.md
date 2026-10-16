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
