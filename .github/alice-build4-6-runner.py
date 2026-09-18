#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-5-runner.py",
    ".github/alice-build4-6-fix.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.6 patches applied")
