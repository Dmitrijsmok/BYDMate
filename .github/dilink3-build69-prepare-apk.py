from pathlib import Path

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

m = Path('app/src/main/AndroidManifest.xml')
t = m.read_text()
if 'android:label="BYDMate"' not in t:
    raise SystemExit('manifest label anchor missing')
m.write_text(t.replace('android:label="BYDMate"', 'android:label="BYDMate DiLink3 Build69"', 1))

print('Build69 field APK identity/signing prepared')
