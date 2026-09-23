"""Run only the requested child process group with a hard wall-clock deadline."""
import argparse
import os
import signal
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--seconds', type=int, default=1800)
p.add_argument('command', nargs=argparse.REMAINDER)
args = p.parse_args()
child = subprocess.Popen(args.command, start_new_session=True)
try:
    code = child.wait(timeout=args.seconds)
except subprocess.TimeoutExpired:
    os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
    code = 124
print(f'bounded command exit={code} deadline={args.seconds}s', flush=True)
sys.exit(code)
