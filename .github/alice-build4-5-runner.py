#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-4-runner.py",
    ".github/alice-build4-5-fix.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.5 patches applied")
