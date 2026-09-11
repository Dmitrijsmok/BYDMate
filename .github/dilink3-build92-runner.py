#!/usr/bin/env python3
import base64
import subprocess
from pathlib import Path

refs = [
    "dilink3-build70-fixed", "dilink3-build71-ai-ui", "dilink3-build72-agent-routing",
    "dilink3-build73-final", "dilink3-build74-aihubmix", "dilink3-build75-minimax",
    "dilink3-build76-openrouter", "dilink3-build77-marusya", "dilink3-build78-voice-timing",
    "dilink3-build79-deep-diagnostics", "dilink3-build80-launch-crashfix",
    "dilink3-build81-steering-recovery", "dilink3-build82-sherpa-streaming",
    "dilink3-build83-update-rebind-streamfix", "dilink3-build84-lowlatency-clauses",
    "dilink3-build85-universal-assistant", "dilink3-build86-assistant-lab",
    "dilink3-build87-native-assistant-handoff", "dilink3-build88-overlay-touchfix",
    "dilink3-build89-yandex-alice-v3", "dilink3-build90-dual-yandex-debug",
    "dilink3-build91-alice-lab", "build92", "dilink3-build66-wizard",
]
subprocess.run(["git", "fetch", "origin", *refs], check=True)

patches = [
    ("dilink3-build70-fixed", ".github/dilink3-build70-fixes.py"),
    ("dilink3-build71-ai-ui", ".github/dilink3-build71-fixes.py"),
    ("dilink3-build72-agent-routing", ".github/dilink3-build72-fixes.py"),
    ("dilink3-build73-final", ".github/dilink3-build73-fixes.py"),
    ("dilink3-build73-final", ".github/dilink3-build73-test-fixes.py"),
    ("dilink3-build73-final", ".github/dilink3-build73-final-hotfix.py"),
    ("dilink3-build74-aihubmix", ".github/dilink3-build74-aihubmix.py"),
    ("dilink3-build75-minimax", ".github/dilink3-build75-minimax.py"),
    ("dilink3-build76-openrouter", ".github/dilink3-build76-openrouter.py"),
    ("dilink3-build77-marusya", ".github/dilink3-build77-marusya.py"),
    ("dilink3-build78-voice-timing", ".github/dilink3-build78-voice-timing.py"),
    ("dilink3-build78-voice-timing", ".github/dilink3-build78-compile-hotfix.py"),
    ("dilink3-build79-deep-diagnostics", ".github/dilink3-build79-deep-diagnostics.py"),
    ("dilink3-build80-launch-crashfix", ".github/dilink3-build80-launch-crashfix.py"),
    ("dilink3-build81-steering-recovery", ".github/dilink3-build81-steering-recovery.py"),
    ("dilink3-build82-sherpa-streaming", ".github/dilink3-build82-sherpa-streaming.py"),
    ("dilink3-build83-update-rebind-streamfix", ".github/dilink3-build83-update-rebind-streamfix.py"),
    ("dilink3-build84-lowlatency-clauses", ".github/dilink3-build84-lowlatency.py"),
    ("dilink3-build85-universal-assistant", ".github/dilink3-build85-universal.py"),
    ("dilink3-build86-assistant-lab", ".github/dilink3-build86-assistant-lab.py"),
    ("dilink3-build87-native-assistant-handoff", ".github/dilink3-build87-native-handoff.py"),
    ("dilink3-build88-overlay-touchfix", ".github/dilink3-build88-overlay-touchfix.py"),
    ("dilink3-build89-yandex-alice-v3", ".github/dilink3-build89-yandex-alice.py"),
    ("dilink3-build90-dual-yandex-debug", ".github/dilink3-build90-dual-yandex-debug.py"),
    ("dilink3-build91-alice-lab", ".github/dilink3-build91-alice-mode.py"),
    ("dilink3-build91-alice-lab", ".github/dilink3-build91-log-share.py"),
    ("dilink3-build91-alice-lab", ".github/dilink3-build91-yandex-permissions.py"),
    ("build92", ".github/dilink3-build92-exact-alice.py"),
]

key_b64 = subprocess.check_output(["git", "show", "origin/dilink3-build66-wizard:.github/dilink3-debug.keystore.b64"])
Path("/tmp/dilink3-field-test.keystore").write_bytes(base64.b64decode(key_b64))

for i, (ref, path) in enumerate(patches):
    out = Path(f"/tmp/build92-patch-{i}.py")
    out.write_bytes(subprocess.check_output(["git", "show", f"origin/{ref}:{path}"]))
    subprocess.run(["python3", str(out)], check=True)

subprocess.run(["git", "diff", "--check"], check=True)
print("Build92 patch chain applied")
