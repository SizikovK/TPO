"""Графики и таблица из финальных HTML и временных CSV Locust."""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
os.environ.setdefault('MPLCONFIGDIR', str(OUT / '.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    summary = []
    stages = sorted(OUT.glob('bmc-*_stats.csv'), key=lambda p: int(p.name.split('-')[1].split('_')[0]))
    stages += sorted(OUT.glob('public-*_stats.csv'))
    for path in stages:
        # CSV обновляется периодически и может не включать последние запросы.
        # Финальный HTML создаётся при завершении и совпадает с консольным итогом.
        html = path.with_name(path.name.replace('_stats.csv', '.html')).read_text()
        marker = 'window.templateArgs = '
        offset = html.index(marker) + len(marker)
        final = json.JSONDecoder().raw_decode(html[offset:])[0]
        rows = final['requests_statistics']
        kind, count = path.name.split('_')[0].split('-')
        for row in rows:
            requests = int(row['num_requests'])
            failures = int(row['num_failures'])
            summary.append({'target': kind, 'users': int(count), 'name': row['name'],
                            'requests': requests, 'failures': failures,
                            'error_percent': failures / requests * 100 if requests else None,
                            'average_ms': float(row['avg_response_time']),
                            'p95_ms': float(row['response_time_percentile_0.95']), 'rps': float(row['total_rps'])})
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    lines = ['| API | Users | Request | Count | Errors | Errors % | Mean ms | p95 ms | RPS |',
             '| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in summary:
        error = 'N/A' if row['error_percent'] is None else f"{row['error_percent']:.2f}"
        lines.append(f"| {row['target']} | {row['users']} | {row['name']} | {row['requests']} | {row['failures']} | {error} | {row['average_ms']:.2f} | {row['p95_ms']:.0f} | {row['rps']:.2f} |")
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    aggregate = [row for row in summary if row['target'] == 'bmc' and row['name'] == 'Aggregated']
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    users = [row['users'] for row in aggregate]
    axes[0].plot(users, [row['average_ms'] for row in aggregate], 'o-', label='Mean')
    axes[0].plot(users, [row['p95_ms'] for row in aggregate], 's-', label='p95')
    axes[0].set_ylabel('Response time, ms'); axes[0].legend()
    axes[1].plot(users, [row['rps'] for row in aggregate], 'o-'); axes[1].set_ylabel('Requests / second')
    axes[2].plot(users, [row['error_percent'] for row in aggregate], 'o-'); axes[2].set_ylabel('Errors, %')
    axes[2].set_ylim(0, max(1, max(row['error_percent'] for row in aggregate) * 1.1))
    for ax in axes:
        ax.set_xlabel('BMC users'); ax.set_xticks(users); ax.grid(alpha=.3)
    fig.suptitle('OpenBMC: measured load stages (40 s each, spawn rate 2/s)')
    fig.tight_layout(); fig.savefig(OUT / 'load-stages.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for path in stages:
        kind, count = path.name.split('_')[0].split('-')
        if kind != 'bmc':
            continue
        history = [row for row in read(path.with_name(path.name.replace('_stats.csv', '_stats_history.csv'))) if row['Name'] == 'Aggregated']
        if not history:
            continue
        origin = float(history[0]['Timestamp'])
        seconds = [float(row['Timestamp']) - origin for row in history]
        label = f'{count} users'
        axes[0].plot(seconds, [float(row['User Count']) for row in history], label=label)
        axes[1].plot(seconds, [float(row['Requests/s']) for row in history], label=label)
        axes[2].plot(seconds, [float(row['Total Average Response Time']) for row in history], label=label)
    for ax, ylabel in zip(axes, ['Active users', 'Requests / second', 'Cumulative mean, ms']):
        ax.set_ylabel(ylabel); ax.grid(alpha=.3); ax.legend()
    axes[-1].set_xlabel('Seconds since stage start')
    fig.tight_layout(); fig.savefig(OUT / 'load-history.png', dpi=160); plt.close(fig)
    stable = [row for row in aggregate if row['requests'] > 0 and row['failures'] == 0]
    print('\n'.join(lines))
    if stable:
        maximum = max(stable, key=lambda row: row['users'])
        print(f"Largest measured zero-error stage: {maximum['users']} users; {maximum['rps']:.2f} RPS; p95 {maximum['p95_ms']:.0f} ms")
    else:
        print('No zero-error BMC stage was observed')
    print('Charts: lab6/results/load-stages.png, lab6/results/load-history.png')


if __name__ == '__main__':
    main()
