#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-identity.py",
    ".github/alice-build4-smarthome.py",
    ".github/alice-build4-agent-master.py",
    ".github/alice-build4-agent-permission.py",
    ".github/alice-build4-native-mirror.py",
    ".github/alice-build4-a11y-recovery.py",
    ".github/alice-build4-yandex-cold.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4 patches applied")
