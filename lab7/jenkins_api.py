"""Запуск и сбор доказательств Jenkins через HTTP API без вывода пароля."""
import argparse
import base64
import http.cookiejar
import json
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
    args = parser.parse_args()
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

    if args.action == 'status':
        data = read_json(BASE + '/api/json?tree=mode,quietingDown,jobs[name,color]')
        print(json.dumps(data, indent=2))
        return 0
    if args.action in ('build', 'validate'):
        crumb = read_json(BASE + '/crumbIssuer/api/json')
        headers = {crumb['crumbRequestField']: crumb['crumb']}
        if args.action == 'validate':
            content = (ROOT / 'Jenkinsfile').read_bytes()
            boundary = 'Lab7JenkinsfileBoundary'
            payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="jenkinsfile"; filename="Jenkinsfile"\r\nContent-Type: text/plain\r\n\r\n'.encode()
                       + content + f'\r\n--{boundary}--\r\n'.encode())
            headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
            output = request(BASE + '/pipeline-model-converter/validate', payload, headers)[0].decode()
            (OUT / 'jenkinsfile-validation.txt').write_text(output)
            print(output)
            return 0 if 'Jenkinsfile successfully validated' in output else 1
        _, response_headers = request(JOB + '/build', b'', headers)
        queue = response_headers['Location']
        (OUT / 'queue.json').write_text(json.dumps({'url': queue}, indent=2))
        print('Pipeline поставлен в очередь: ' + queue)
        return 0
    if args.number:
        build = JOB + '/' + str(args.number)
    else:
        queue = json.loads((OUT / 'queue.json').read_text())['url']
        deadline = time.monotonic() + 300
        while True:
            data = read_json(queue + 'api/json')
            if data.get('executable'):
                build = JOB + '/' + str(data['executable']['number'])
                break
            if data.get('cancelled') or time.monotonic() > deadline:
                raise RuntimeError('Очередь отменена или сборка не началась за 300 с')
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
    print('Доказательства сохранены: ' + str(folder.relative_to(ROOT.parent)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
