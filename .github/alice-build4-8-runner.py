#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-7-runner.py",
    ".github/alice-build4-8-fix.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.8 patches applied")
