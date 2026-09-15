#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-8-runner.py",
    ".github/alice-build4-2-autostart.py",
    ".github/alice-build4-9-stable.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.9 stable patches applied; autostart popup restored")
