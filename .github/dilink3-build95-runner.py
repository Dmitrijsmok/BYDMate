#!/usr/bin/env python3
import subprocess
from pathlib import Path

subprocess.run(["git", "fetch", "origin", "build94", "build95"], check=True)

base = Path("/tmp/build94-runner.py")
base.write_bytes(subprocess.check_output([
    "git", "show", "origin/build94:.github/dilink3-build94-runner.py"
]))
subprocess.run(["python3", str(base)], check=True)

patch = Path("/tmp/build95-steering-fix.py")
patch.write_bytes(subprocess.check_output([
    "git", "show", "origin/build95:.github/dilink3-build95-steering-fix.py"
]))
subprocess.run(["python3", str(patch)], check=True)
subprocess.run(["git", "diff", "--check"], check=True)
print("Build95 patch chain applied")
