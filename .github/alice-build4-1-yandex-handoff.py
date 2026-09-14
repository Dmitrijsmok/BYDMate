#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-1-base.py",
    ".github/alice-build4-2-identity.py",
    ".github/alice-build4-2-yandex-speed.py",
    ".github/alice-build4-2-master-gate.py",
    ".github/alice-build4-2-vrassistant-sync.py",
    ".github/alice-build4-2-autostart.py",
    ".github/alice-build4-2-boot-prewarm.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.2 patches applied")
