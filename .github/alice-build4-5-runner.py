#!/usr/bin/env python3
import subprocess

steps = [
    ".github/alice-build4-4-runner.py",
    ".github/alice-build4-5-vrassistant-helper.py",
    ".github/alice-build4-5-main-without-helper.py",
]

for step in steps:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

subprocess.run(["git", "diff", "--check"], check=True)
print("Alice Build 4.5 applied: Build95 recovery + vrassistant block + one-press cold Alice + audio duck")
