#!/usr/bin/env python3
"""Restore the owner key in CI; stage only independently verified release artifacts."""
import argparse
import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE_ID = "com.bydmate.dilink3.app"
EXPECTED_CERT_SHA256 = "B839BC11CFAD61EC6A89DE10DC0E5EB74CBA25C57DA116ADE30BF4A89D70C054"
SECRET_NAMES = (
    "BYDMATE_KEYSTORE_BASE64", "BYDMATE_KEYSTORE_PASSWORD",
    "BYDMATE_KEY_PASSWORD",
)
BUILD_TOOLS_VERSION = "34.0.0"


class Failure(Exception):
    """Only deliberately non-sensitive messages may be raised here."""


@dataclass(frozen=True)
class BuildInfo:
    version_name: str
    version_code: int

    @property
    def apk_name(self):
        return f"BYDMate-dilink3-v{self.version_name}.apk"


def read_build_info(root):
    source = (root / "app/build.gradle.kts").read_text()

    def one(pattern):
        matches = re.findall(pattern, source, re.MULTILINE)
        if len(matches) != 1:
            raise Failure("Expected a single literal Gradle identity/version declaration")
        return matches[0]

    if one(r'^\s*applicationId\s*=\s*"([^"]+)"\s*$') != PACKAGE_ID:
        raise Failure("Unexpected Gradle application ID")
    if one(r'^\s*namespace\s*=\s*"([^"]+)"\s*$') != "com.bydmate.app":
        raise Failure("Unexpected Gradle namespace")
    return BuildInfo(one(r'^\s*versionName\s*=\s*"(\d+\.\d+\.\d+(?:-asr-lab\.\d+)?)"\s*$'),
                     int(one(r'^\s*versionCode\s*=\s*(\d+)\s*$')))


def checked(command, label, *, cwd=None, env=None):
    # Never forward tool output, commands, or exception reprs from a secret-bearing process.
    try:
        result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError:
        raise Failure(f"{label}: could not start tool") from None
    if result.returncode:
        raise Failure(f"{label} failed (exit {result.returncode}); tool output withheld")
    return result.stdout


def require_trusted_push(env):
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/main", "GITHUB_REPOSITORY": "Dmitrijsmok/BYDMate"}
    if any(env.get(key) != value for key, value in expected.items()):
        raise Failure("Signing is restricted to owner-repository push events on main")


def require_trusted_lab_push(env):
    branch = "refs/heads/lab/v4.0.1-speech-preroll"
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": branch, "GITHUB_REPOSITORY": "Dmitrijsmok/BYDMate",
                "GITHUB_ACTOR": "Dmitrijsmok", "GITHUB_TRIGGERING_ACTOR": "Dmitrijsmok",
                "GITHUB_REF_PROTECTED": "true",
                "GITHUB_WORKFLOW_REF": f"Dmitrijsmok/BYDMate/.github/workflows/ci.yml@{branch}"}
    if any(env.get(key) != value for key, value in expected.items()):
        raise Failure("Lab signing requires an owner push to the exact protected laboratory branch")


def restore_keystore(env, target):
    if any(not env.get(name) for name in SECRET_NAMES):
        raise Failure("All three ALICE_SIGNING secrets must be mapped and nonempty")
    try:
        data = base64.b64decode("".join(env["BYDMATE_KEYSTORE_BASE64"].split()), validate=True)
    except (ValueError, binascii.Error):
        raise Failure("Keystore secret is not valid base64") from None
    if not data:
        raise Failure("Decoded keystore is empty")
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as file:
        file.write(data)


def discover_key_alias(keystore, env):
    # Use the Java KeyStore API rather than parsing localized keytool listings or
    # assuming an alias. Base64 transports arbitrary alias characters without ambiguity.
    helper = Path(__file__).with_name("SigningKeyInventory.java")
    output = checked(["java", str(helper), str(keystore)], "Keystore inventory", env=env)
    try:
        entries = json.loads(output)
        if not isinstance(entries, list):
            raise ValueError
        aliases = set()
        matches = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"alias", "type", "sha256"}:
                raise ValueError
            alias = base64.b64decode(entry["alias"], validate=True).decode("utf-8")
            if not alias or "\0" in alias or alias in aliases:
                raise ValueError
            aliases.add(alias)
            if entry["type"] not in ("private", "trusted", "other"):
                raise ValueError
            if not re.fullmatch(r"(?:[0-9A-F]{64})?", entry["sha256"]):
                raise ValueError
            if entry["type"] == "private" and entry["sha256"] == EXPECTED_CERT_SHA256:
                matches.append(alias)
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise Failure("Keystore inventory is invalid or ambiguous") from None
    if len(matches) != 1:
        raise Failure("Keystore must contain exactly one private-key entry matching the pinned certificate")
    return matches[0]


def verify_keystore(keystore, env):
    alias = discover_key_alias(keystore, env)
    common = ["-keystore", str(keystore), "-storepass:env", "BYDMATE_KEYSTORE_PASSWORD",
              "-alias", alias]
    cert = checked(["keytool", "-exportcert", *common], "Keystore certificate export", env=env)
    if hashlib.sha256(cert).hexdigest().upper() != EXPECTED_CERT_SHA256:
        raise Failure("Keystore certificate does not match the pinned permanent certificate")
    # A CSR proves private-key access without generating a key or exporting private material.
    # It is held in memory and discarded; the release build must also accept the key password.
    checked(["keytool", "-certreq", *common, "-keypass:env", "BYDMATE_KEY_PASSWORD"],
            "Keystore private-key access", env=env)
    print(f"Verified keystore certificate SHA-256: {EXPECTED_CERT_SHA256}")
    return alias


def write_properties(target, properties):
    # Java Properties.load(InputStream) uses ISO-8859-1 plus Unicode escapes.
    # Escaping every UTF-16 code unit preserves spaces, newlines, backslashes and non-ASCII passwords.
    def escape(value):
        hex_units = value.encode("utf-16-be").hex()
        return "".join("\\u" + hex_units[i:i + 4] for i in range(0, len(hex_units), 4))

    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as file:
            for key, value in properties.items():
                file.write(f"{key}={escape(value)}\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def verify_apk(apk, info, tools):
    if apk.name != info.apk_name or not apk.is_file():
        raise Failure("Expected exact OTA-compatible APK filename is missing")
    signature = checked([str(tools / "apksigner"), "verify", "--verbose", "--print-certs", str(apk)],
                        "APK signature verification").decode("utf-8")
    certs = re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F:]+)$',
                       signature, re.MULTILINE)
    if [cert.replace(":", "").upper() for cert in certs] != [EXPECTED_CERT_SHA256]:
        raise Failure("APK must have exactly the pinned permanent signing certificate")
    badging = checked([str(tools / "aapt"), "dump", "badging", str(apk)], "APK identity inspection").decode("utf-8")
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.MULTILINE)
    if not package or package.groups() != (PACKAGE_ID, str(info.version_code), info.version_name):
        raise Failure("APK package/version differs from the expected Gradle configuration")
    manifest = checked([str(tools / "aapt"), "dump", "xmltree", str(apk), "AndroidManifest.xml"],
                       "APK release manifest inspection").decode("utf-8")
    if "E: manifest " not in manifest or "E: application " not in manifest:
        raise Failure("APK manifest inspection did not return a manifest/application tree")
    for line in manifest.splitlines():
        if "android:debuggable(" in line or "android:testOnly(" in line:
            if not re.search(r'=\(type 0x12\)0x0\s*$', line):
                raise Failure("Debug/test-only APKs (or unknown flag encodings) are forbidden")
    return {"filename": apk.name, "package": PACKAGE_ID, "version_name": info.version_name,
            "version_code": info.version_code, "debuggable": False, "certificate_sha256": EXPECTED_CERT_SHA256,
            "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "size_bytes": apk.stat().st_size}


def verify_release_metadata(directory, info):
    metadata = json.loads((directory / "output-metadata.json").read_text())
    elements = metadata.get("elements", [])
    if (metadata.get("variantName") != "release" or metadata.get("applicationId") != PACKAGE_ID
            or metadata.get("artifactType", {}).get("type") != "APK" or len(elements) != 1):
        raise Failure("Gradle output metadata is not a single release APK for the expected package")
    expected = {"outputFile": info.apk_name, "versionName": info.version_name, "versionCode": info.version_code}
    if any(elements[0].get(key) != value for key, value in expected.items()):
        raise Failure("Release output metadata differs from Gradle versions/filename")


def build(root, env, *, lab=False):
    if lab:
        require_trusted_lab_push(env)
    else:
        require_trusted_push(env)
    info = read_build_info(root)
    if lab and (info.version_name != "4.0.1-asr-lab.1" or info.version_code != 100002):
        raise Failure("Unexpected laboratory build identity")
    props = root / "keystore.properties"
    if props.exists():
        raise Failure("Refusing to overwrite an existing owner signing configuration")
    runner_temp = Path(env["RUNNER_TEMP"]).resolve()
    stage = runner_temp / "bydmate-verified-apk"
    if stage.exists():
        raise Failure("Refusing to reuse a potentially stale artifact staging directory")
    tools = Path(env["ANDROID_HOME"]) / "build-tools" / BUILD_TOOLS_VERSION
    with tempfile.TemporaryDirectory(prefix="bydmate-signing-", dir=runner_temp) as directory:
        keystore = Path(directory) / "owner.jks"
        restore_keystore(env, keystore)
        alias = verify_keystore(keystore, env)
        created = False
        try:
            write_properties(props, {"storeFile": str(keystore), "storePassword": env["BYDMATE_KEYSTORE_PASSWORD"],
                                     "keyAlias": alias, "keyPassword": env["BYDMATE_KEY_PASSWORD"]})
            created = True
            checked(["./gradlew", ":app:assembleRelease", "--no-daemon", "--no-configuration-cache",
                     "--no-build-cache", "--console=plain"], "Signed release build", cwd=root,
                    env={key: value for key, value in env.items() if key not in SECRET_NAMES})
        finally:
            if created:
                props.unlink(missing_ok=True)
    # Signing material has been removed before any artifact verification/staging/upload.
    directory = root / "app/build/outputs/apk/release"
    verify_release_metadata(directory, info)
    apk = directory / info.apk_name
    evidence = verify_apk(apk, info, tools)
    evidence.update({"variant": "release", "commit": env["GITHUB_SHA"], "laboratory": lab})
    stage.mkdir(mode=0o700)
    shutil.copyfile(apk, stage / info.apk_name)
    (stage / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--build-tools", type=Path)
    parser.add_argument("--lab", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.action == "build":
            build(root, dict(os.environ), lab=args.lab)
        else:
            if args.apk is None or args.build_tools is None:
                raise Failure("verify requires --apk and --build-tools")
            print(json.dumps(verify_apk(args.apk, read_build_info(root), args.build_tools), indent=2))
    except Failure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except Exception:
        # Do not let unexpected exception messages disclose secret-bearing arguments or files.
        print("ERROR: Release pipeline failed; no artifact may be uploaded. Details withheld.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
