#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
for tool in perf nmon vmstat ps pgrep curl python sudo; do
    command -v "$tool" >/dev/null || { echo "Не найден $tool"; exit 1; }
done
mapfile -t qemu_pids < <(pgrep -x qemu-system-arm)
if (( ${#qemu_pids[@]} != 1 )); then
    echo 'Нужен ровно один запущенный qemu-system-arm.'
    exit 1
fi
qemu_pid=${qemu_pids[0]}
read -rsp 'Пароль OpenBMC: ' bmc_password
echo
http_code=$(curl --noproxy '*' -ksS --connect-timeout 5 --max-time 10 \
    -u "root:$bmc_password" -o /dev/null -w '%{http_code}' \
    https://127.0.0.1:2443/redfish/v1/Systems)
[[ $http_code == 200 ]] || { echo "Redfish вернул HTTP $http_code"; exit 1; }
echo 'Для аппаратных счётчиков perf потребуется sudo.'
sudo -v
result_dir=$(mktemp -d "$PWD/results-XXXXXX")
{
    date -Is
    uname -srmo
    perf --version
    nmon -V
    ps -p "$qemu_pid" -o pid,args
} > "$result_dir/environment.txt"

measure() {
    local phase=$1 vm_pid perf_pid
    echo "Замер $phase: 15 секунд. Не выполняй другие действия в OpenBMC."
    mkdir "$result_dir/$phase"
    vmstat 1 16 > "$result_dir/$phase/vmstat.txt" &
    vm_pid=$!
    sudo -n perf stat -e cycles,instructions,cache-misses -p "$qemu_pid" \
        -- sleep 15 2> "$result_dir/$phase/perf.txt" &
    perf_pid=$!
    nmon -F "$result_dir/$phase/network.nmon" -s 1 -c 15
    if [[ $phase == load ]]; then
        (
            stop_at=$((SECONDS + 15))
            while (( SECONDS < stop_at )); do
                curl --noproxy '*' -ksS --connect-timeout 2 --max-time 3 \
                    -u "root:$bmc_password" -o /dev/null -w '%{http_code}\n' \
                    https://127.0.0.1:2443/redfish/v1/Systems || true
            done
        ) > "$result_dir/$phase/http-codes.txt" 2> "$result_dir/$phase/curl-errors.txt" &
        load_pid=$!
    fi
    for ((sample=0; sample<15; sample++)); do
        ps -p "$qemu_pid" -o rss= >> "$result_dir/$phase/rss-kib.txt"
        sleep 1
    done
    wait "$vm_pid"
    if wait "$perf_pid"; then
        echo 0 > "$result_dir/$phase/perf-exit.txt"
    else
        echo "$?" > "$result_dir/$phase/perf-exit.txt"
    fi
    if [[ $phase == load ]]; then wait "$load_pid"; fi
}
measure idle
measure load
unset bmc_password
python - "$result_dir" <<'PY'
import pathlib, statistics, sys
root = pathlib.Path(sys.argv[1])
lines = ['Режим | CPU хоста, % (100-id) | RSS QEMU, МиБ']
for phase in ('idle', 'load'):
    folder = root / phase
    rows = [r.split() for r in (folder/'vmstat.txt').read_text().splitlines()
            if r.strip() and r.split()[0].isdigit()][1:]
    cpu = statistics.mean(100 - float(r[14]) for r in rows)
    rss = statistics.mean(map(float, (folder/'rss-kib.txt').read_text().split())) / 1024
    lines.append(f'{phase} | {cpu:.2f} | {rss:.2f}')
    if (folder/'perf-exit.txt').read_text().strip() != '0':
        lines.append(f'ВНИМАНИЕ: perf для {phase} завершился с ошибкой; см. perf.txt')
codes = (root/'load/http-codes.txt').read_text().splitlines()
lines.append(f'Redfish: HTTP 200 — {codes.count("200")} из {len(codes)} запросов')
summary = '\n'.join(lines) + '\n'
(root/'summary.txt').write_text(summary)
print(summary)
PY
echo "Результаты сохранены: $result_dir"
