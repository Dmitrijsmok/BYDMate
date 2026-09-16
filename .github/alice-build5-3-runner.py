#!/usr/bin/env python3
import subprocess

for step in [
    ".github/alice-build5-2-runner.py",
    ".github/alice-build5-3-final.py",
]:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 5.3 v3.16.0 integration patches applied")
