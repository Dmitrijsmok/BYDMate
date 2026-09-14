#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-6-runner.py",
    ".github/alice-build4-7-anchorfix.py",
    ".github/alice-build4-7-fix.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 4.7 patches applied")
