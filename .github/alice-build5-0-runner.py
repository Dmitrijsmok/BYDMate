#!/usr/bin/env python3
import subprocess

for step in [
    ".github/alice-build4-9-runner.py",
    ".github/alice-build5-0-command-bridge.py",
    ".github/alice-build5-0-test-compat.py",
]:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 5.0 command bridge patches applied")
