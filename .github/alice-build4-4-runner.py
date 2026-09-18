#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-3-runner.py",
    ".github/alice-build4-4-silent-recovery.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.4 patches applied")
