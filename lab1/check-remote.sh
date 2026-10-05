#!/usr/bin/env bash
# Run on a separate Linux machine with curl and ipmitool installed.
set -u

if [[ $# -ne 1 || ! $1 =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]]; then
    echo "Usage: bash check-remote.sh <IPv4-or-hostname-of-QEMU-host>" >&2
    exit 2
fi

for program in curl ipmitool; do
    if ! command -v "$program" >/dev/null 2>&1; then
        echo "Missing required program: $program" >&2
        exit 1
    fi
done

bmc_host=$1
result_dir=$(mktemp -d ./openbmc-remote-XXXXXX) || exit 1
{
    date -Is
    hostname
    uname -srmo
    echo "QEMU host: $bmc_host"
    if command -v ip >/dev/null 2>&1; then
        ip -brief address
    fi
} > "$result_dir/client.txt"

echo "IPMI: enter the OpenBMC password when prompted."
ipmitool -I lanplus -H "$bmc_host" -p 2623 -U root -a fru print \
    > "$result_dir/ipmi.txt" 2> "$result_dir/ipmi-stderr.txt"
ipmi_status=$?
cat "$result_dir/ipmi.txt" "$result_dir/ipmi-stderr.txt"

echo "Redfish: enter the OpenBMC password when prompted."
curl -k -sS -i --connect-timeout 10 --max-time 30 \
    -u root "https://${bmc_host}:2443/redfish/v1/Systems" \
    > "$result_dir/redfish.txt"
redfish_status=$?
cat "$result_dir/redfish.txt"
printf '\nIPMI exit code: %s\ncurl exit code: %s\n' \
    "$ipmi_status" "$redfish_status" | tee "$result_dir/status.txt"
echo "Results saved in: $result_dir"
