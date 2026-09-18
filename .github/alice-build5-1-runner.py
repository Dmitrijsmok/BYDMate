#!/usr/bin/env python3
import subprocess

for step in [
    ".github/alice-build5-0-runner.py",
    ".github/alice-build5-1-app-bridge.py",
]:
    print(f"==> {step}", flush=True)
    subprocess.run(["python3", step], check=True)

print("Alice Build 5.1 app bridge patches applied")
