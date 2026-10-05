"""Лабораторная 5: проверки реального Redfish и IPMI, без подмены датчиков."""
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import time

import pytest
import requests
import urllib3

BASE = os.getenv('BMC_URL', 'https://127.0.0.1:3443').rstrip('/')
USER = os.getenv('BMC_USER', 'root')
PASSWORD = os.getenv('BMC_PASSWORD', '0penBmc')
OUT = Path(__file__).parent / 'results'
OUT.mkdir(exist_ok=True)
LOG = logging.getLogger(__name__)
SYSTEM = '/redfish/v1/Systems/system'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def call(session, method, path, **kwargs):
    try:
        response = session.request(method, BASE + path, timeout=30, verify=False, **kwargs)
    except requests.RequestException as exc:
        pytest.fail(f'{method} {path}: {type(exc).__name__}: {exc}')
    LOG.info('%s %s -> HTTP %s', method, path, response.status_code)
    # Не сохраняем токены, пароль и содержимое сессии.
    if 'SessionService/Sessions' not in path:
        filename = re.sub(r'[^\w-]', '_', method + path) + '.txt'
        (OUT / filename).write_text(f'HTTP {response.status_code}\n{response.text}\n')
    return response


def get(session, path):
    response = call(session, 'GET', path)
    assert response.status_code == 200, response.text
    try:
        return response.json()
    except ValueError:
        pytest.fail(f'{path}: ответ не является JSON')


@pytest.fixture(scope='module')
def redfish_session():
    session = requests.Session()
    session.trust_env = False
    response = call(session, 'POST', '/redfish/v1/SessionService/Sessions',
                    json={'UserName': USER, 'Password': PASSWORD})
    # 201 разрешён только при подготовке fixture, тест ниже требует ровно 200.
    assert response.status_code in (200, 201), response.text
    token = response.headers.get('X-Auth-Token')
    location = response.headers.get('Location')
    assert token, 'Нет X-Auth-Token'
    session.headers['X-Auth-Token'] = token
    try:
        yield session, response
    finally:
        if location:
            from urllib.parse import urlsplit
            path = urlsplit(location).path
            if path.startswith('/redfish/v1/SessionService/Sessions/'):
                result = call(session, 'DELETE', path)
                if result.status_code not in (200, 204):
                    LOG.error('Удаление сессии: HTTP %s', result.status_code)
        session.close()


def test_authentication(redfish_session):
    _, response = redfish_session
    assert response.status_code == 200, f'По заданию HTTP 200, фактически {response.status_code}'
    assert response.headers.get('X-Auth-Token'), 'Нет токена сессии'


def test_system_information(redfish_session):
    data = get(redfish_session[0], SYSTEM)
    assert 'Status' in data and isinstance(data['Status'], dict)
    assert 'PowerState' in data
    LOG.info('Status=%s; PowerState=%s', data['Status'], data['PowerState'])


def test_power_on(redfish_session):
    session = redfish_session[0]
    before = get(session, SYSTEM)['PowerState']
    assert before == 'Off', f'Для проверки перехода Off -> On нужно Off; получено {before}'
    response = call(session, 'POST', SYSTEM + '/Actions/ComputerSystem.Reset', json={'ResetType': 'On'})
    deadline = time.monotonic() + float(os.getenv('POWER_TIMEOUT', '60'))
    states = []
    while True:
        state = get(session, SYSTEM)['PowerState']
        states.append(state)
        if state == 'On' or time.monotonic() >= deadline:
            break
        time.sleep(2)
    LOG.info('Включение: HTTP %s; состояния=%s', response.status_code, states)
    assert response.status_code == 202 and states[-1] == 'On', (
        f'Ожидались HTTP 202 и PowerState=On; HTTP {response.status_code}, состояния={states}')


@pytest.fixture(scope='module')
def cpu_temperatures(redfish_session):
    session = redfish_session[0]
    chassis = get(session, '/redfish/v1/Chassis')
    sensors = []
    for member in chassis['Members']:
        data = get(session, member['@odata.id'])
        thermal = data.get('Thermal')
        if not thermal:
            continue
        for sensor in get(session, thermal['@odata.id']).get('Temperatures', []):
            if sensor.get('PhysicalContext') == 'CPU' or re.search(r'cpu|proc', sensor.get('Name', ''), re.I):
                sensors.append(sensor)
    if not sensors:
        pytest.skip('Blocked: в Redfish Thermal нет датчиков температуры CPU')
    return sensors


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def test_cpu_temperature_normal(cpu_temperatures):
    for sensor in cpu_temperatures:
        reading = sensor.get('ReadingCelsius')
        assert number(reading), f'Нет числовой температуры CPU: {sensor}'
        assert sensor.get('Status', {}).get('Health') == 'OK', sensor
        assert sensor.get('Status', {}).get('State') == 'Enabled', sensor
        upper = sensor.get('UpperThresholdNonCritical')
        if not number(upper):
            pytest.skip(f"Blocked: для {sensor['Name']} не задан UpperThresholdNonCritical")
        assert reading < upper, f'{reading} °C >= {upper} °C'
        lower = sensor.get('LowerThresholdNonCritical')
        if number(lower):
            assert reading > lower, f'{reading} °C <= {lower} °C'
        LOG.info('%s: %s °C, верхняя граница нормы %s °C', sensor['Name'], reading, upper)


def test_cpu_sensors_redfish_ipmi(cpu_temperatures):
    # Для отличающихся имён задаётся явное отображение {Redfish Name: IPMI Name}.
    mapping = json.loads(os.getenv('CPU_SENSOR_MAP', '{}'))
    tolerance = float(os.getenv('CPU_TEMP_TOLERANCE', '1.0'))
    assert math.isfinite(tolerance) and tolerance >= 0
    command = ['ipmitool', '-I', 'lanplus', '-H', os.getenv('IPMI_HOST', '127.0.0.1'),
               '-p', os.getenv('IPMI_PORT', '3623'), '-U', USER, '-E', 'sensor', 'list']
    try:
        result = subprocess.run(command, env={**os.environ, 'IPMI_PASSWORD': PASSWORD},
                                text=True, capture_output=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.fail(f'Ошибка IPMI: {exc}')
    (OUT / 'ipmi-sensors.txt').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    rows = {}
    for line in result.stdout.splitlines():
        fields = [part.strip() for part in line.split('|')]
        if len(fields) >= 4:
            rows.setdefault(fields[0], []).append(fields)
    for sensor in cpu_temperatures:
        name = mapping.get(sensor['Name'], sensor['Name'])
        matches = rows.get(name, [])
        assert len(matches) == 1, f'Нет однозначного соответствия IPMI для {name}'
        row = matches[0]
        assert row[2] == 'degrees C' and row[3] == 'ok', row
        try:
            ipmi = float(row[1])
        except ValueError:
            pytest.fail(f'IPMI не вернул числовое показание: {row}')
        redfish = sensor.get('ReadingCelsius')
        assert number(redfish) and math.isfinite(ipmi)
        assert abs(redfish - ipmi) <= tolerance, f'{name}: Redfish={redfish}, IPMI={ipmi}'
        LOG.info('%s: Redfish=%s °C, IPMI=%s °C, допуск=%s °C', name, redfish, ipmi, tolerance)
