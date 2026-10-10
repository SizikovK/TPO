"""Запуск и сбор доказательств Jenkins через HTTP API без вывода пароля."""
import argparse
import base64
import http.cookiejar
import json
import sys
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
BASE = 'http://127.0.0.1:18080'
JOB = BASE + '/job/openbmc-ci'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'validate', 'build', 'watch', 'collect'])
    parser.add_argument('--number', type=int)
    parser.add_argument('--wait-ready', type=float, default=180, help='Ожидание запуска Jenkins, секунды')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    settings = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if '=' in line)
    encoded = base64.b64encode((settings['JENKINS_ADMIN_USER'] + ':' + settings['JENKINS_ADMIN_PASSWORD']).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(url, data=None, headers=None):
        headers = {**(headers or {}), 'Authorization': 'Basic ' + encoded}
        with opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=30) as response:
            return response.read(), dict(response.headers)

    def read_json(url):
        return json.loads(request(url)[0])

    deadline = time.monotonic() + args.wait_ready
    announced = False
    while True:
        try:
            ready = read_json(BASE + '/api/json?tree=mode,quietingDown,jobs[name,color]')
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (502, 503, 504):
                raise
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            if time.monotonic() >= deadline:
                raise RuntimeError('Jenkins не готов. Проверь docker compose ps и logs; повтори команду после запуска.') from exc
            if not announced:
                print('Ожидание готовности Jenkins…', file=sys.stderr, flush=True)
                announced = True
            time.sleep(min(2, max(0, deadline - time.monotonic())))

    if args.action == 'status':
        print(json.dumps(ready, indent=2))
        return 0
    if args.action in ('build', 'validate'):
        crumb = read_json(BASE + '/crumbIssuer/api/json')
        headers = {crumb['crumbRequestField']: crumb['crumb']}
        if args.action == 'validate':
            payload = urllib.parse.urlencode({'jenkinsfile': (ROOT / 'Jenkinsfile').read_text()}).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            output = request(BASE + '/pipeline-model-converter/validate', payload, headers)[0].decode()
            (OUT / 'jenkinsfile-validation.txt').write_text(output)
            print(output)
            return 0 if 'Jenkinsfile successfully validated' in output else 1
        job = read_json(JOB + '/api/json?tree=property[parameterDefinitions[name]]')
        parameterized = any(prop.get('parameterDefinitions') for prop in job.get('property', []))
        endpoint = '/buildWithParameters' if parameterized else '/build'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        _, response_headers = request(JOB + endpoint, b'', headers)
        queue = urllib.parse.urljoin(BASE, response_headers['Location'])
        queue_id = int(urllib.parse.urlparse(queue).path.rstrip('/').split('/')[-1])
        (OUT / 'queue.json').write_text(json.dumps({'url': queue, 'id': queue_id}, indent=2))
        print('Pipeline поставлен в очередь: ' + queue)
        return 0
    if args.number:
        build = JOB + '/' + str(args.number)
    else:
        if not (OUT / 'queue.json').exists():
            raise RuntimeError('Нет сохранённой очереди. Выполни build или укажи --number НОМЕР.')
        saved_queue = json.loads((OUT / 'queue.json').read_text())
        if saved_queue.get('number'):
            build = JOB + '/' + str(saved_queue['number'])
        else:
            queue = saved_queue['url']
            deadline = time.monotonic() + 1800
            last_queue_reason = None
            while True:
                try:
                    data = read_json(queue + 'api/json')
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise
                    exc.close()
                    # Jenkins удаляет очередь; ищем именно её сборку, а не любую последнюю.
                    queue_id = saved_queue.get('id', int(urllib.parse.urlparse(queue).path.rstrip('/').split('/')[-1]))
                    history = read_json(JOB + '/api/json?tree=builds[number,queueId]{0,100}')
                    match = next((item for item in history.get('builds', []) if item.get('queueId') == queue_id), None)
                    if not match:
                        raise RuntimeError('Очередь удалена и связанная сборка не найдена. Выполни build либо укажи --number НОМЕР.') from exc
                    data = {'executable': {'number': match['number']}}
                if data.get('executable'):
                    number = data['executable']['number']
                    build = JOB + '/' + str(number)
                    saved_queue['number'] = number
                    # Запись очереди Jenkins позднее удаляется; номер сборки сохраняем.
                    (OUT / 'queue.json').write_text(json.dumps(saved_queue, indent=2))
                    break
                if data.get('cancelled') or time.monotonic() > deadline:
                    raise RuntimeError('Очередь отменена или сборка не началась за 30 минут')
                reason = data.get('why')
                if reason and reason != last_queue_reason:
                    print('Ожидание очереди: ' + reason, flush=True)
                    last_queue_reason = reason
                time.sleep(2)
    if args.action == 'watch':
        deadline = time.monotonic() + 1800
        last = None
        while time.monotonic() < deadline:
            data = read_json(build + '/api/json?tree=number,building,result,duration')
            stages = read_json(build + '/wfapi/describe')
            status = [(stage['name'], stage['status']) for stage in stages.get('stages', [])]
            if status != last:
                print(f"Build #{data['number']}: {status}", flush=True)
                last = status
            if not data['building']:
                print(f"Build #{data['number']}: {data['result']}; duration={data['duration']} ms", flush=True)
                return 0
            time.sleep(10)
        raise TimeoutError('Pipeline не завершился за 30 минут')
    info = read_json(build + '/api/json?tree=number,building,result,duration,timestamp,artifacts[fileName,relativePath]')
    if info['building']:
        raise RuntimeError('Сборка ещё выполняется; сбор артефактов отложен')
    folder = OUT / f"build-{info['number']}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'build.json').write_text(json.dumps(info, indent=2))
    stages = read_json(build + '/wfapi/describe')
    (folder / 'stages.json').write_text(json.dumps(stages, indent=2))
    (folder / 'console.txt').write_bytes(request(build + '/consoleText')[0])
    tests = read_json(build + '/testReport/api/json?tree=failCount,skipCount,passCount,totalCount,suites[cases[className,name,status,errorDetails]]')
    (folder / 'tests.json').write_text(json.dumps(tests, indent=2))
    for artifact in info['artifacts']:
        relative = Path(artifact['relativePath']).relative_to('lab7/results')
        if '..' in relative.parts:
            raise RuntimeError('Некорректный путь артефакта')
        target = folder / 'artifacts' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(request(build + '/artifact/' + urllib.parse.quote(artifact['relativePath']))[0])
    print(f"Build #{info['number']}: {info['result']}; артефактов: {len(info['artifacts'])}")
    print(f"JUnit: passed={tests['passCount']}, failed={tests['failCount']}, skipped={tests['skipCount']}")
    print('Доказательства сохранены: ' + str(folder))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        exc.close()
        print(f'Ошибка Jenkins: HTTP {exc.code} ({exc.reason}). Проверь доступ и задание openbmc-ci.', file=sys.stderr)
        raise SystemExit(1)
    except (urllib.error.URLError, RuntimeError, OSError, ValueError, KeyError) as exc:
        print(f'Ошибка: {exc}', file=sys.stderr)
        raise SystemExit(1)
