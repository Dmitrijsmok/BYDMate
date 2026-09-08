from pathlib import Path

FIELD_PACKAGE = "com.bydmate.app.dilink3prodtest"

p = Path('app/build.gradle.kts')
s = p.read_text()

signing_anchor = "    signingConfigs {\n        if (keystorePropsFile.exists()) {\n"
signing_repl = (
    "    signingConfigs {\n"
    "        create(\"dilink3ProdTest\") {\n"
    "            storeFile = file(\"/tmp/dilink3-field-test.keystore\")\n"
    "            storePassword = \"dilink3debug\"\n"
    "            keyAlias = \"dilink3debug\"\n"
    "            keyPassword = \"dilink3debug\"\n"
    "        }\n"
    "        if (keystorePropsFile.exists()) {\n"
)
if signing_anchor not in s:
    raise SystemExit('signingConfigs anchor missing')
s = s.replace(signing_anchor, signing_repl, 1)

build_anchor = "    buildTypes {\n        release {\n"
build_repl = (
    "    buildTypes {\n"
    "        debug {\n"
    "            applicationIdSuffix = \".dilink3prodtest\"\n"
    "            versionNameSuffix = \"-dilink3-production-build69\"\n"
    "            signingConfig = signingConfigs.getByName(\"dilink3ProdTest\")\n"
    "        }\n"
    "        release {\n"
)
if build_anchor not in s:
    raise SystemExit('buildTypes anchor missing')
s = s.replace(build_anchor, build_repl, 1)

if '        versionCode = 443' not in s:
    raise SystemExit('versionCode anchor missing')
s = s.replace('        versionCode = 443', '        versionCode = 60019', 1)
p.write_text(s)

# A side-by-side APK must make every narrow helper operation target THIS APK, not an installed
# com.bydmate.app production copy. Otherwise the test UI writes one package's prefs while the
# AccessibilityService that actually receives 304/327 belongs to another package.
protocol = Path('app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt')
t = protocol.read_text()
replacements = {
    'const val APP_PACKAGE = "com.bydmate.app"':
        f'const val APP_PACKAGE = "{FIELD_PACKAGE}"',
    '"com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"':
        f'"{FIELD_PACKAGE}/com.bydmate.app.cluster.SteeringWheelKeyService"',
    '"com.bydmate.app/com.bydmate.app.media.MediaSessionListenerService"':
        f'"{FIELD_PACKAGE}/com.bydmate.app.media.MediaSessionListenerService"',
}
for old, new in replacements.items():
    if old not in t:
        raise SystemExit(f'helper field-package anchor missing: {old}')
    t = t.replace(old, new, 1)
protocol.write_text(t)

m = Path('app/src/main/AndroidManifest.xml')
t = m.read_text()
if 'android:label="BYDMate"' not in t:
    raise SystemExit('manifest label anchor missing')
m.write_text(t.replace('android:label="BYDMate"', 'android:label="BYDMate DiLink3 Build69"', 1))

print('Build69 field APK identity/signing/helper targets prepared')
