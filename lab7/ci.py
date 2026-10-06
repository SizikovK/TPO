"""Этапы Jenkins: настоящий QEMU, существующие pytest/Selenium и Locust."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'lab7/results'
PID_FILE = OUT / 'qemu-process.json'
IMAGE = os.getenv('BMC_FIRMWARE', '/opt/openbmc/image.static.mtd')
BASE = 'https://127.0.0.1:3443'


def write_report(folder, title, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'summary.md').write_text(f'# {title}\n\n{text}\n')


def stop():
    if not PID_FILE.exists():
        print('Нет запущенного этим Pipeline QEMU')
        return
    state = json.loads(PID_FILE.read_text())
    pid = state['pid']
    path = Path(f'/proc/{pid}/cmdline')
    if path.exists():
        command = path.read_bytes().decode(errors='replace')
        if 'qemu-system-arm' in command and state['image'] in command:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 15
            while path.exists() and time.monotonic() < deadline:
                time.sleep(.2)
            if path.exists() and 'qemu-system-arm' in path.read_bytes().decode(errors='replace'):
                os.kill(pid, signal.SIGKILL)
            print(f'QEMU PID {pid} остановлен')
        elif command:
            raise RuntimeError('PID принадлежит другому процессу; остановка отменена')
    PID_FILE.unlink()


def start(folder):
    stop()
    folder.mkdir(parents=True, exist_ok=True)
    if not Path(IMAGE).is_file():
        raise RuntimeError(f'Нет образа OpenBMC: {IMAGE}')
    command = ['qemu-system-arm', '-M', 'romulus-bmc', '-m', '256', '-snapshot',
               '-drive', f'file={IMAGE},format=raw,if=mtd', '-nographic',
               '-net', 'nic', '-net', 'user,hostfwd=tcp:127.0.0.1:3443-:443,hostfwd=udp:127.0.0.1:3623-:623']
    (folder / 'command.txt').write_text(' '.join(command) + '\n')
    with (folder / 'boot.log').open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True,
                                   env={**os.environ, 'JENKINS_NODE_COOKIE': 'lab7-openbmc'})
    PID_FILE.write_text(json.dumps({'pid': process.pid, 'image': IMAGE}))
    username = os.getenv('BMC_USER', 'root')
    password = os.getenv('BMC_PASSWORD', '0penBmc')
    auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    deadline = time.monotonic() + 240
    attempts = 0
    last_error = ''
    while time.monotonic() < deadline:
        attempts += 1
        if process.poll() is not None:
            raise RuntimeError(f'QEMU завершился: {process.returncode}; см. boot.log')
        try:
            request = urllib.request.Request(BASE + '/redfish/v1/Systems/system',
                                             headers={'Authorization': 'Basic ' + auth})
            with opener.open(request, timeout=5) as response:
                data = json.load(response)
                assert response.status == 200 and 'PowerState' in data and 'Status' in data
            (folder / 'system.json').write_text(json.dumps(data, indent=2))
            write_report(folder, 'Запуск OpenBMC в QEMU',
                         f'QEMU PID: {process.pid}. API доступен: HTTP 200.\n\n'
                         f'PowerState: {data["PowerState"]}. Попыток проверки готовности: {attempts}.\n\n'
                         'Режим -snapshot: исходная прошивка не изменяется.')
            print(f'QEMU готов: HTTP 200; PowerState={data["PowerState"]}; attempts={attempts}', flush=True)
            return
        except Exception as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            time.sleep(2)
    raise RuntimeError(f'API не готов за 240 с: {last_error}')


def run_tests(kind):
    folder = OUT / kind
    folder.mkdir(parents=True, exist_ok=True)
    if kind == 'api':
        command = [sys.executable, '-m', 'pytest', 'lab5/test_redfish.py', '-v', '-ra', '--tb=short',
                   f'--junitxml={folder / "junit.xml"}', '-o', f'log_file={folder / "pytest.log"}']
        source = ROOT / 'lab5/results'
    else:
        # API-тест запрашивал включение; свежий QEMU изолирует предусловия WebUI.
        start(folder / 'qemu')
        command = [sys.executable, '-m', 'pytest', 'lab4/test_webui.py', '-v', '-ra', '--tb=short',
                   f'--junitxml={folder / "junit.xml"}']
        source = ROOT / 'lab4/results'
    (folder / 'command.txt').write_text(' '.join(command) + '\n')
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=600)
    (folder / 'output.txt').write_text(result.stdout)
    if source.exists():
        shutil.copytree(source, folder / 'details', dirs_exist_ok=True)
    (folder / 'exit-code.txt').write_text(f'{result.returncode}\n')
    write_report(folder, f'{kind}: pytest',
                 f'Код завершения: {result.returncode}.\n\nПолный вывод: output.txt. '
                 'Результаты отдельных тестов: junit.xml. '
                 'Ошибки и пропуски отражены без подмены результатов.')
    print(result.stdout, flush=True)
    return result.returncode


def load():
    folder = OUT / 'load'
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'locust', '-f', 'lab6/locustfile.py', 'OpenBMCUser',
               '--headless', '-u', '10', '-r', '2', '-t', '30s', '--stop-timeout', '20',
               '--csv', str(folder / 'locust'), '--csv-full-history', '--html', str(folder / 'locust.html'),
               '--only-summary']
    (folder / 'command.txt').write_text(' '.join(command) + '\n')
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=120)
    (folder / 'output.txt').write_text(result.stdout)
    (folder / 'exit-code.txt').write_text(f'{result.returncode}\n')
    write_report(folder, 'Нагрузочное тестирование OpenBMC',
                 f'10 пользователей, 2 пользователя/с, 30 с. Код завершения: {result.returncode}.\n\n'
                 'Проверяются system information и PowerState. Отчёты: locust.html, CSV и output.txt.')
    print(result.stdout, flush=True)
    return result.returncode


def prepare():
    # Удаляем прошлые доказательства только в отдельном Jenkins workspace.
    if os.getenv('WORKSPACE') != str(ROOT):
        raise RuntimeError('prepare разрешён только внутри Jenkins WORKSPACE')
    for path in (OUT, ROOT / 'lab4/results', ROOT / 'lab5/results', ROOT / 'lab6/results'):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    commands = [['python', '--version'], ['qemu-system-arm', '--version'], ['firefox', '--version'],
                ['geckodriver', '--version'], ['ipmitool', '-V'], ['locust', '--version'],
                ['git', 'rev-parse', 'HEAD'], ['sha256sum', IMAGE]]
    output = []
    for command in commands:
        result = subprocess.run(command, text=True, capture_output=True)
        output.append('$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'Проверка зависимости завершилась ошибкой: {command}')
    write_report(OUT / 'environment', 'Окружение CI', '\n```text\n' + '\n'.join(output) + '\n```')
    print('\n'.join(output), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['prepare', 'qemu', 'api', 'webui', 'load', 'stop'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        if args.step == 'prepare':
            prepare()
        elif args.step == 'qemu':
            start(OUT / 'qemu')
        elif args.step in ('api', 'webui'):
            return run_tests(args.step)
        elif args.step == 'load':
            return load()
        else:
            stop()
    except Exception as exc:
        write_report(OUT / args.step, f'Ошибка этапа {args.step}', f'{type(exc).__name__}: {exc}')
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
