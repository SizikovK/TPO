#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec qemu-system-arm -M romulus-bmc -m 256 -nographic -snapshot \
  -drive file=investigation/romulus-20250902/image.static.mtd,format=raw,if=mtd \
  -net nic -net user,hostfwd=tcp:127.0.0.1:3222-:22,hostfwd=tcp:127.0.0.1:3443-:443,hostfwd=udp:127.0.0.1:3623-:623
