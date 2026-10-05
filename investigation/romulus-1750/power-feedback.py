#!/usr/bin/env python3
"""Diagnostic Romulus PSU model: GPIO D2 follows D1 AND R1. No host OS emulation."""
import json
import socket
import sys
import time


def run(path):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(5)
        sock.connect(path)
        with sock.makefile('rwb', buffering=0) as stream:
            def receive():
                line = stream.readline()
                if not line:
                    raise EOFError('QEMU closed QMP')
                return json.loads(line)

            def command(name, **arguments):
                stream.write((json.dumps({'execute': name, 'arguments': arguments}) + '\n').encode())
                while True:
                    result = receive()
                    if 'error' in result:
                        raise RuntimeError(result['error'])
                    if 'return' in result:
                        return result['return']

            receive()
            command('qmp_capabilities')
            gpio = '/machine/soc/gpio'
            previous = None
            while True:
                up = command('qom-get', path=gpio, property='gpioD1')
                software_good = command('qom-get', path=gpio, property='gpioR1')
                good = bool(up and software_good)
                actual = command('qom-get', path=gpio, property='gpioD2')
                if actual != good:
                    command('qom-set', path=gpio, property='gpioD2', value=good)
                if good != previous:
                    print(f'Simulated PSU: D1={int(up)} R1={int(software_good)} -> D2/PGOOD={int(good)}', flush=True)
                    previous = good
                time.sleep(0.2)


if __name__ == '__main__':
    try:
        run(sys.argv[1])
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
