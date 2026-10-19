"""Fail-closed signing tests. Fixtures/mocks never generate an Android signing key."""
import base64
import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "app/build.gradle.kts").write_text('''
namespace = "com.bydmate.app"
applicationId = "com.bydmate.dilink3.app"
versionCode = 100001
versionName = "1.0.0"
''')
        self.info = release.read_build_info(self.root)
        self.apk = self.root / self.info.apk_name
        self.apk.write_bytes(b"APK fixture, not a signed APK")
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main", "GITHUB_REPOSITORY": "Dmitrijsmok/BYDMate",
            "GITHUB_SHA": "a" * 40, "RUNNER_TEMP": str(self.root / "runner"),
            "ANDROID_HOME": str(self.root / "sdk"),
            "BYDMATE_KEYSTORE_BASE64": base64.b64encode(b"keystore fixture").decode(),
            "BYDMATE_KEYSTORE_PASSWORD": "fixture-store-password",
            "BYDMATE_KEY_PASSWORD": "fixture-key-password",
        }
        (self.root / "runner").mkdir()

    def apk_tools(self, package=release.PACKAGE_ID, version="1.0.0", code="100001",
                  debug="", cert=release.EXPECTED_CERT_SHA256, valid=True):
        def invoke(command, label, **kwargs):
            if command[0].endswith("apksigner"):
                if not valid:
                    raise release.Failure("APK signature verification failed")
                return f"Signer #1 certificate SHA-256 digest: {cert}\n".encode()
            if "badging" in command:
                return f"package: name='{package}' versionCode='{code}' versionName='{version}'\n".encode()
            return f"E: manifest (line=1)\n  E: application (line=2)\n{debug}".encode()
        return patch.object(release, "checked", side_effect=invoke)

    def test_gradle_identity_and_filename(self):
        self.assertEqual("BYDMate-dilink3-v1.0.0.apk", self.info.apk_name)
        self.assertEqual(100001, self.info.version_code)

    def test_unexpected_or_ambiguous_gradle_config_fails(self):
        path = self.root / "app/build.gradle.kts"
        original = path.read_text()
        for text in [original.replace(release.PACKAGE_ID, "wrong.package"),
                     original + '\nversionCode = 100002', original.replace('"1.0.0"', 'versionFromEnv')]:
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(release.Failure):
                    release.read_build_info(self.root)

    def test_push_main_in_owner_repository_only(self):
        release.require_trusted_push(self.env)
        for key, value in [("GITHUB_ACTIONS", "false"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("GITHUB_REF", "refs/heads/topic"), ("GITHUB_REPOSITORY", "fork/BYDMate")]:
            with self.subTest(key=key), self.assertRaises(release.Failure):
                release.require_trusted_push(dict(self.env, **{key: value}))

    def test_each_missing_secret_fails_without_creating_keystore(self):
        for key in release.SECRET_NAMES:
            target = self.root / "missing.jks"
            with self.subTest(key=key), self.assertRaises(release.Failure):
                release.restore_keystore(dict(self.env, **{key: ""}), target)
            self.assertFalse(target.exists())

    def test_invalid_base64_fails_closed(self):
        with self.assertRaises(release.Failure):
            release.restore_keystore(dict(self.env, BYDMATE_KEYSTORE_BASE64="not base64!"), self.root / "bad.jks")

    def test_restoration_is_private_and_accepts_wrapped_base64(self):
        target = self.root / "fixture.jks"
        env = dict(self.env, BYDMATE_KEYSTORE_BASE64="\n" + self.env["BYDMATE_KEYSTORE_BASE64"] + "\n")
        release.restore_keystore(env, target)
        self.assertEqual(b"keystore fixture", target.read_bytes())
        self.assertEqual(0o600, target.stat().st_mode & 0o777)

    def inventory(self, entries=None):
        if entries is None:
            entries = [("fixture-alias", "private", release.EXPECTED_CERT_SHA256)]
        return json.dumps([{"alias": base64.b64encode(alias.encode()).decode(),
                            "type": kind, "sha256": digest}
                           for alias, kind, digest in entries]).encode()

    def test_unique_pinned_private_alias_is_discovered_without_alias_secret(self):
        alias = "owner alias=ü\nsecond line"
        inventory = self.inventory([
            ("certificate-only", "trusted", release.EXPECTED_CERT_SHA256),
            ("other-key", "private", "00" * 32),
            (alias, "private", release.EXPECTED_CERT_SHA256),
        ])
        with patch.object(release, "checked", return_value=inventory):
            self.assertEqual(alias, release.discover_key_alias(self.root / "fixture.jks", self.env))
        self.assertEqual(3, len(release.SECRET_NAMES))
        self.assertNotIn("BYDMATE_KEY_ALIAS", release.SECRET_NAMES)

    def test_missing_ambiguous_or_certificate_only_matches_are_rejected(self):
        fingerprint = release.EXPECTED_CERT_SHA256
        for entries in [[], [("wrong", "private", "00" * 32)],
                        [("certificate-only", "trusted", fingerprint)],
                        [("secret-key", "other", "")],
                        [("one", "private", fingerprint), ("two", "private", fingerprint)],
                        [("same", "private", fingerprint), ("same", "private", fingerprint)]]:
            with self.subTest(entries=entries), patch.object(release, "checked", return_value=self.inventory(entries)) as tool:
                with self.assertRaises(release.Failure):
                    release.verify_keystore(self.root / "fixture.jks", self.env)
                self.assertEqual(1, tool.call_count)

    def test_malformed_inventory_is_rejected_without_echoing_it(self):
        for inventory in [b"secret-bearing garbage", b"null", b"{}", b"[{}]",
                          b'[{"alias":"!", "type":"private", "sha256":"bad"}]']:
            with self.subTest(inventory=inventory), patch.object(release, "checked", return_value=inventory):
                with self.assertRaises(release.Failure) as error:
                    release.discover_key_alias(self.root / "fixture.jks", self.env)
                self.assertNotIn("secret-bearing", str(error.exception))

    def test_certificate_mismatch_stops_before_private_key_probe(self):
        with patch.object(release, "checked", side_effect=[self.inventory(), b"wrong certificate"]) as tool:
            with self.assertRaises(release.Failure):
                release.verify_keystore(self.root / "fixture.jks", self.env)
            self.assertEqual(2, tool.call_count)

    def test_matching_certificate_also_checks_private_key_access_without_password_arguments(self):
        with patch.object(release, "checked", side_effect=[self.inventory(), b"public certificate", b"CSR"]) as tool, \
                patch.object(release.hashlib, "sha256") as digest, contextlib.redirect_stdout(io.StringIO()) as output:
            digest.return_value.hexdigest.return_value = release.EXPECTED_CERT_SHA256.lower()
            self.assertEqual("fixture-alias", release.verify_keystore(self.root / "fixture.jks", self.env))
            self.assertEqual(3, tool.call_count)
            self.assertIn("-certreq", tool.call_args.args[0])
            self.assertNotIn("fixture-alias", output.getvalue())
            for call in tool.call_args_list:
                self.assertNotIn(self.env["BYDMATE_KEYSTORE_PASSWORD"], call.args[0])
                self.assertNotIn(self.env["BYDMATE_KEY_PASSWORD"], call.args[0])

    def test_private_key_access_failure_is_not_accepted(self):
        with patch.object(release, "checked", side_effect=[self.inventory(), b"public certificate",
                          release.Failure("Private-key access failed")]), \
                patch.object(release.hashlib, "sha256") as digest:
            digest.return_value.hexdigest.return_value = release.EXPECTED_CERT_SHA256.lower()
            with self.assertRaises(release.Failure):
                release.verify_keystore(self.root / "fixture.jks", self.env)

    def test_inventory_helper_rejects_invalid_keystore_without_exposing_details(self):
        # Run the real Java source launcher; no keystore or signing identity is generated.
        helper = Path(release.__file__).with_name("SigningKeyInventory.java")
        target = self.root / "invalid.jks"
        target.write_bytes(b"not a keystore")
        result = subprocess.run(["java", str(helper), str(target)],
                                env=dict(os.environ, BYDMATE_KEYSTORE_PASSWORD="fixture-store-password"),
                                capture_output=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"Keystore inventory failed\n", result.stderr)

    def test_workflow_maps_only_existing_repository_secrets(self):
        workflow = Path(release.__file__).parents[1] / ".github/workflows/ci.yml"
        source = workflow.read_text()
        for internal, repository in [("BYDMATE_KEYSTORE_BASE64", "ALICE_SIGNING_KEYSTORE_B64"),
                                     ("BYDMATE_KEYSTORE_PASSWORD", "ALICE_SIGNING_STORE_PASSWORD"),
                                     ("BYDMATE_KEY_PASSWORD", "ALICE_SIGNING_KEY_PASSWORD")]:
            self.assertIn(internal + ": ${{ secrets." + repository + " }}", source)
        self.assertNotIn("secrets.BYDMATE_", source)
        self.assertNotIn("BYDMATE_KEY_ALIAS", source)

    def test_properties_escape_special_characters_and_are_private(self):
        target = self.root / "keystore.properties"
        release.write_properties(target, {"keyPassword": " leading=colon:\\\nü🔐"})
        self.assertEqual(0o600, target.stat().st_mode & 0o777)
        self.assertEqual("keyPassword=", target.read_text().split('\\u')[0])
        escaped = target.read_text().split('=', 1)[1].strip()
        units = bytes.fromhex(escaped.replace('\\u', ''))
        self.assertEqual(" leading=colon:\\\nü🔐", units.decode("utf-16-be"))
        with self.assertRaises(FileExistsError):
            release.write_properties(target, {"keyPassword": "replacement"})

    def test_valid_release_evidence_contains_only_public_metadata(self):
        with self.apk_tools():
            result = release.verify_apk(self.apk, self.info, self.root)
        self.assertEqual(release.EXPECTED_CERT_SHA256, result["certificate_sha256"])
        self.assertFalse(result["debuggable"])
        self.assertEqual(self.info.apk_name, result["filename"])

    def test_wrong_package_versions_or_certificate_are_rejected(self):
        for kwargs in [{"package": "com.bydmate.app"}, {"version": "1.0.1"}, {"code": "1"},
                       {"cert": "00" * 32}, {"cert": ""}, {"valid": False}]:
            with self.subTest(kwargs=kwargs), self.apk_tools(**kwargs), self.assertRaises(release.Failure):
                release.verify_apk(self.apk, self.info, self.root)

    def test_debug_or_test_only_apk_is_rejected(self):
        for attribute in ["debuggable", "testOnly"]:
            with self.subTest(attribute=attribute), self.apk_tools(
                debug=f"A: android:{attribute}(0x0101000f)=(type 0x12)0xffffffff"
            ), self.assertRaises(release.Failure):
                release.verify_apk(self.apk, self.info, self.root)

    def test_explicit_false_debug_flag_is_accepted(self):
        with self.apk_tools(debug="A: android:debuggable(0x0101000f)=(type 0x12)0x0"):
            release.verify_apk(self.apk, self.info, self.root)

    def test_wrong_filename_is_rejected(self):
        wrong = self.root / "DiLink3Friendly-v1.0.0.apk"
        wrong.write_bytes(b"fixture")
        with self.assertRaises(release.Failure):
            release.verify_apk(wrong, self.info, self.root)

    def test_multiple_signers_or_missing_manifest_are_rejected(self):
        fingerprint = f"Signer #1 certificate SHA-256 digest: {release.EXPECTED_CERT_SHA256}\n"
        with patch.object(release, "checked", return_value=(fingerprint + fingerprint).encode()), \
                self.assertRaises(release.Failure):
            release.verify_apk(self.apk, self.info, self.root)
        identity = f"package: name='{release.PACKAGE_ID}' versionCode='100001' versionName='1.0.0'\n"
        with patch.object(release, "checked", side_effect=[fingerprint.encode(), identity.encode(), b""]), \
                self.assertRaises(release.Failure):
            release.verify_apk(self.apk, self.info, self.root)

    def metadata(self):
        return {"variantName": "release", "applicationId": release.PACKAGE_ID, "artifactType": {"type": "APK"},
                "elements": [{"outputFile": self.info.apk_name, "versionName": "1.0.0", "versionCode": 100001}]}

    def test_release_metadata_must_match_variant_package_filename_and_versions(self):
        path = self.root / "output-metadata.json"
        path.write_text(json.dumps(self.metadata()))
        release.verify_release_metadata(self.root, self.info)
        changes = [("variantName", "debug"), ("applicationId", "wrong.package"),
                   ("artifactType", {"type": "BUNDLE"}), ("elements", [])]
        for key, value in changes:
            metadata = dict(self.metadata(), **{key: value})
            path.write_text(json.dumps(metadata))
            with self.subTest(key=key), self.assertRaises(release.Failure):
                release.verify_release_metadata(self.root, self.info)
        for key, value in [("outputFile", "wrong.apk"), ("versionName", "1.0.1"), ("versionCode", 1)]:
            metadata = self.metadata()
            metadata["elements"][0][key] = value
            path.write_text(json.dumps(metadata))
            with self.subTest(key=key), self.assertRaises(release.Failure):
                release.verify_release_metadata(self.root, self.info)

    def test_successful_build_stages_only_verified_apk_and_public_evidence(self):
        directory = self.root / "app/build/outputs/apk/release"
        directory.mkdir(parents=True)
        (directory / self.info.apk_name).write_bytes(b"fixture APK")
        (directory / "output-metadata.json").write_text(json.dumps(self.metadata()))
        public = {"filename": self.info.apk_name, "certificate_sha256": release.EXPECTED_CERT_SHA256}
        def check_build(command, label, **kwargs):
            self.assertIn(":app:assembleRelease", command)
            self.assertNotIn(":app:assembleDebug", command)
            properties = (self.root / "keystore.properties").read_text()
            encoded = next(line.split("=", 1)[1] for line in properties.splitlines() if line.startswith("keyAlias="))
            self.assertEqual("discovered-alias", bytes.fromhex(encoded.replace('\\u', '')).decode("utf-16-be"))
            self.assertTrue(all(key not in kwargs["env"] for key in release.SECRET_NAMES))
            return b""

        with patch.object(release, "verify_keystore", return_value="discovered-alias"), \
                patch.object(release, "checked", side_effect=check_build), \
                patch.object(release, "verify_apk", return_value=public), contextlib.redirect_stdout(io.StringIO()):
            release.build(self.root, self.env)
        stage = self.root / "runner/bydmate-verified-apk"
        self.assertEqual({self.info.apk_name, "verification.json"}, {path.name for path in stage.iterdir()})
        self.assertEqual("release", json.loads((stage / "verification.json").read_text())["variant"])
        self.assertFalse((self.root / "keystore.properties").exists())
        self.assertEqual([stage], list((self.root / "runner").iterdir()))

    def test_ambiguous_alias_prevents_build_and_cleans_restored_keystore(self):
        fingerprint = release.EXPECTED_CERT_SHA256
        inventory = self.inventory([("one", "private", fingerprint), ("two", "private", fingerprint)])
        with patch.object(release, "checked", return_value=inventory) as tool:
            with self.assertRaises(release.Failure):
                release.build(self.root, self.env)
            self.assertEqual(1, tool.call_count)
            self.assertEqual("java", tool.call_args.args[0][0])
        self.assertFalse((self.root / "keystore.properties").exists())
        self.assertEqual([], list((self.root / "runner").iterdir()))

    def test_invalid_apk_after_build_is_never_staged(self):
        with patch.object(release, "verify_keystore", return_value="discovered-alias"), patch.object(release, "checked", return_value=b""), \
                patch.object(release, "verify_release_metadata"), \
                patch.object(release, "verify_apk", side_effect=release.Failure("wrong certificate")):
            with self.assertRaises(release.Failure):
                release.build(self.root, self.env)
        self.assertFalse((self.root / "keystore.properties").exists())
        self.assertEqual([], list((self.root / "runner").iterdir()))

    def test_partial_properties_are_removed_on_write_failure(self):
        path = self.root / "keystore.properties"
        with self.assertRaises(AttributeError):
            release.write_properties(path, {"storePassword": "fixture", "keyPassword": None})
        self.assertFalse(path.exists())

    def test_failed_private_key_probe_prevents_build_and_cleans_restored_keystore(self):
        with patch.object(release, "verify_keystore", side_effect=release.Failure("private key inaccessible")), \
                patch.object(release, "checked") as tool:
            with self.assertRaises(release.Failure):
                release.build(self.root, self.env)
        tool.assert_not_called()
        self.assertFalse((self.root / "keystore.properties").exists())
        self.assertEqual([], list((self.root / "runner").iterdir()))

    def test_failed_build_cleans_secrets_and_does_not_stage_an_artifact(self):
        with patch.object(release, "verify_keystore", return_value="discovered-alias"), \
                patch.object(release, "checked", side_effect=release.Failure("build failed")) as tool:
            with self.assertRaises(release.Failure):
                release.build(self.root, self.env)
        self.assertFalse((self.root / "keystore.properties").exists())
        self.assertEqual([], list((self.root / "runner").iterdir()))
        self.assertIn(":app:assembleRelease", tool.call_args.args[0])
        self.assertTrue(all(key not in tool.call_args.kwargs["env"] for key in release.SECRET_NAMES))

    def test_existing_owner_properties_are_not_overwritten(self):
        props = self.root / "keystore.properties"
        props.write_text("owner configuration")
        with self.assertRaises(release.Failure):
            release.build(self.root, self.env)
        self.assertEqual("owner configuration", props.read_text())

    def test_tool_failure_does_not_echo_output_or_command_secrets(self):
        with patch.object(release.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stdout = b"private material"
            run.return_value.stderr = b"password"
            with self.assertRaises(release.Failure) as error:
                release.checked(["tool", "password"], "Probe")
        self.assertNotIn("password", str(error.exception))
        self.assertNotIn("private material", str(error.exception))


if __name__ == "__main__":
    unittest.main()
