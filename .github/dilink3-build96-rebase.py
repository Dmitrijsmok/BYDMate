#!/usr/bin/env python3
import subprocess
from pathlib import Path

REPO = Path.cwd()
OLD_BASE_REF = "origin/dilink3-production-v3143"
UPSTREAM_URL = "https://github.com/AndyShaman/BYDMate.git"
UPSTREAM_SHA = "194d837f701d03fd24b50a9ea0bcd17b73e7fd5a"  # v3.15.2
VERSION_CODE = "60046"
VERSION_SUFFIX = "-dilink3-production-build96"


def run(cmd, cwd=None, capture=False):
    print("+", " ".join(str(x) for x in cmd))
    if capture:
        return subprocess.check_output(cmd, cwd=cwd, text=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build96 anchor missing: {label}")
    return text.replace(old, new, 1)


# Fetch our patch-chain refs and the current upstream release line.
run(["git", "fetch", "origin", "build95", "dilink3-production-v3143"])
remotes = run(["git", "remote"], capture=True).split()
if "upstream" not in remotes:
    run(["git", "remote", "add", "upstream", UPSTREAM_URL])
run(["git", "fetch", "upstream", "main"])

# Pin the rebase to the release commit we audited. It is still an actual rebase:
# upstream v3.15.2 is the source tree, while our Build95 delta is replayed on top.
run(["git", "cat-file", "-e", f"{UPSTREAM_SHA}^{{commit}}"])

# Materialize the exact Build95 field tree from the frozen v3.14.3 production base.
old = Path("/tmp/bydmate-build96-old")
if old.exists():
    subprocess.run(["git", "worktree", "remove", "--force", str(old)], check=False)
run(["git", "worktree", "add", "--detach", str(old), OLD_BASE_REF])
try:
    build95_runner = Path("/tmp/build95-runner-for-rebase.py")
    build95_runner.write_text(run([
        "git", "show", "origin/build95:.github/dilink3-build95-runner.py"
    ], capture=True))
    run(["python3", str(build95_runner)], cwd=old)

    # Stage everything so newly-created files are included. app/build.gradle.kts is
    # intentionally excluded: upstream changed versioning after v3.14.3, so Build96
    # reapplies only the field identity/signing changes to the new v3.15.2 file.
    run(["git", "add", "-A"], cwd=old)
    patch = Path("/tmp/build95-on-v3152.patch")
    with patch.open("w") as fh:
        print("+ git diff --cached --binary (excluding app/build.gradle.kts)")
        subprocess.run(
            ["git", "diff", "--cached", "--binary", "--", ".", ":(exclude)app/build.gradle.kts"],
            cwd=old,
            check=True,
            stdout=fh,
            text=True,
        )
finally:
    run(["git", "worktree", "remove", "--force", str(old)])

# Move the build workspace to upstream v3.15.2 and replay our complete field delta.
run(["git", "checkout", "--detach", UPSTREAM_SHA])
run(["git", "reset", "--hard", UPSTREAM_SHA])
try:
    run(["git", "apply", "--3way", "--index", "/tmp/build95-on-v3152.patch"])
except subprocess.CalledProcessError:
    subprocess.run(["git", "status", "--short"], check=False)
    subprocess.run(["git", "diff", "--cc"], check=False)
    raise

# Reapply update-compatible field APK identity to the new upstream Gradle file.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(
    s,
    "    signingConfigs {\n        if (keystorePropsFile.exists()) {\n",
    "    signingConfigs {\n"
    "        create(\"dilink3ProdTest\") {\n"
    "            storeFile = file(\"/tmp/dilink3-field-test.keystore\")\n"
    "            storePassword = \"dilink3debug\"\n"
    "            keyAlias = \"dilink3debug\"\n"
    "            keyPassword = \"dilink3debug\"\n"
    "        }\n"
    "        if (keystorePropsFile.exists()) {\n",
    "field signing config",
)
s = once(
    s,
    "    buildTypes {\n        release {\n",
    "    buildTypes {\n"
    "        debug {\n"
    "            applicationIdSuffix = \".dilink3prodtest\"\n"
    f"            versionNameSuffix = \"{VERSION_SUFFIX}\"\n"
    "            signingConfig = signingConfigs.getByName(\"dilink3ProdTest\")\n"
    "        }\n"
    "        release {\n",
    "field debug build type",
)
import re
s, n = re.subn(r"(?m)^\s*versionCode\s*=\s*\d+\s*$", f"        versionCode = {VERSION_CODE}", s, count=1)
if n != 1:
    raise SystemExit("Build96 could not set versionCode")
# Keep upstream versionName (3.15.2) intentionally.
p.write_text(s)
run(["git", "add", str(p)])

# Cosmetic build identity only; do NOT rename the Build95 migration preference key,
# because cars upgrading from Build95 must keep their steering-ownership choice.
manifest = Path("app/src/main/AndroidManifest.xml")
ms = manifest.read_text()
if 'android:label="BYDMate DiLink3 Build95"' in ms:
    ms = ms.replace('android:label="BYDMate DiLink3 Build95"', 'android:label="BYDMate DiLink3 Build96"', 1)
elif 'android:label="BYDMate"' in ms:
    ms = ms.replace('android:label="BYDMate"', 'android:label="BYDMate DiLink3 Build96"', 1)
else:
    raise SystemExit("Build96 manifest label anchor missing")
manifest.write_text(ms)
run(["git", "add", str(manifest)])

settings = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
ss = settings.read_text()
ss = ss.replace('Assistant Lab · Build95', 'Assistant Lab · Build96', 1)
settings.write_text(ss)
run(["git", "add", str(settings)])

# The author's hidden Alice/Smart Home integration must survive the rebase untouched.
alice_polling = "app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt"
run(["git", "diff", "--exit-code", UPSTREAM_SHA, "--", alice_polling])

# Sanity / whitespace.
run(["git", "diff", "--cached", "--check"])
print("Build96 rebase applied successfully: upstream v3.15.2 + Build95 field delta")
