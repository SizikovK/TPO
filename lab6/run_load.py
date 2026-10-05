"""Повторяемые ступени нагрузки; команды и полный вывод пишутся в transcript.md."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'lab6/results'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', default='40s')
    parser.add_argument('--users', type=int, nargs='+', default=[1, 5, 10, 20])
    parser.add_argument('--public', action='store_true', help='Дополнительно публичные API: 10 пользователей')
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    exit_code = 0
    with (RESULTS / 'transcript.md').open('w') as transcript:
        stages = [('bmc', count, 'OpenBMCUser') for count in args.users]
        if args.public:
            stages.append(('public', 10, 'PublicAPIUser'))
        for kind, count, user_class in stages:
            prefix = f'lab6/results/{kind}-{count}'
            command = [sys.executable, '-m', 'locust', '-f', 'lab6/locustfile.py', user_class,
                       '--headless', '-u', str(count), '-r', '2', '-t', args.duration,
                       '--csv', prefix, '--csv-full-history', '--html', prefix + '.html',
                       '--stop-timeout', '20', '--only-summary']
            shown = shlex.join(command)
            print(f'RUN: {shown}', flush=True)
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=180)
            if result.returncode:
                exit_code = 1
            (RESULTS / f'{kind}-{count}-output.txt').write_text(result.stdout)
            transcript.write(f'```bash\n{shown}\n```\n\n```text\n{result.stdout}\nExit code: {result.returncode}\n```\n\n')
            transcript.flush()
            print(result.stdout, flush=True)
            print(f'EXIT CODE: {result.returncode}', flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
