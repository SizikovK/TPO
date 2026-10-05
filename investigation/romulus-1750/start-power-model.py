#!/usr/bin/env python3
"""Run a disposable Romulus BMC with a diagnostic PSU model, not a POWER host."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix='romulus-power-') as temporary:
        qmp = str(Path(temporary) / 'qmp.sock')
        command = [
            'qemu-system-arm', '-M', 'romulus-bmc', '-m', '256', '-snapshot',
            '-drive', f'file={BASE / "obmc-phosphor-image-romulus.static.mtd"},format=raw,if=mtd',
            '-nographic', '-qmp', f'unix:{qmp},server=on,wait=off',
            '-net', 'nic', '-net', 'user,hostfwd=tcp:127.0.0.1:3222-:22,hostfwd=tcp:127.0.0.1:3443-:443,hostfwd=udp:127.0.0.1:3623-:623',
        ]
        for bus in (4, 5):
            for address in ('0x70', '0x73'):
                command += ['-device', f'isl69260,bus=aspeed.i2c.bus.{bus},address={address}']
        print('Experimental PSU simulation. POWER CPU/host OS are NOT emulated. Exit: Ctrl+A, X.', flush=True)
        feedback = None
        # Keep the disposable flash overlay inside the disposable directory.
        with open(BASE / 'power-feedback.log', 'a') as log:
            qemu = subprocess.Popen(command, env={**os.environ, 'TMPDIR': temporary})
            try:
                deadline = time.monotonic() + 15
                while not Path(qmp).exists():
                    if qemu.poll() is not None:
                        return qemu.returncode
                    if time.monotonic() >= deadline:
                        raise RuntimeError('QMP socket did not appear')
                    time.sleep(0.1)
                feedback = subprocess.Popen(
                    [sys.executable, str(BASE / 'power-feedback.py'), qmp],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                while qemu.poll() is None:
                    if feedback.poll() is not None:
                        raise RuntimeError('Power model stopped; see power-feedback.log')
                    time.sleep(0.2)
                return qemu.returncode
            finally:
                for child in (feedback, qemu):
                    if child is not None and child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
