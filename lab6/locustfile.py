"""Лабораторная №6: реальные GET-запросы OpenBMC и двух публичных API."""
import os

from locust import HttpUser, between, task

TIMEOUT = 15


def json_response(response):
    """Ошибка HTTP/сети или некорректный JSON учитывается как failure Locust."""
    if response.status_code != 200:
        response.failure(f'HTTP {response.status_code}: {response.error or response.reason}')
        return None
    try:
        data = response.json()
        if data is None:
            response.failure('Response JSON is null')
        return data
    except ValueError:
        response.failure('Response is not JSON')
        return None


class OpenBMCUser(HttpUser):
    host = os.getenv('BMC_URL', 'https://127.0.0.1:3443')
    wait_time = between(1, 3)

    def on_start(self):
        self.client.trust_env = False  # Локальный BMC не отправляется через HTTP proxy.
        self.client.verify = False  # Самоподписанный сертификат учебного BMC.
        self.client.auth = (os.getenv('BMC_USER', 'root'), os.getenv('BMC_PASSWORD', '0penBmc'))

    @task
    def system_information(self):
        with self.client.get('/redfish/v1/Systems/system', name='BMC: system information',
                             timeout=TIMEOUT, catch_response=True) as response:
            data = json_response(response)
            if data is not None and not (isinstance(data, dict) and
                                         isinstance(data.get('Status'), dict) and data.get('Id')):
                response.failure('Missing system Id or Status')

    @task
    def power_state(self):
        # Читаем состояние, не переключаем питание во время нагрузочного теста.
        with self.client.get('/redfish/v1/Systems/system', name='BMC: PowerState',
                             timeout=TIMEOUT, catch_response=True) as response:
            data = json_response(response)
            states = {'On', 'Off', 'PoweringOn', 'PoweringOff', 'Paused'}
            if data is not None and not (isinstance(data, dict) and data.get('PowerState') in states):
                response.failure('Missing or invalid PowerState')


class PublicAPIUser(HttpUser):
    host = 'https://jsonplaceholder.typicode.com'
    wait_time = between(3, 5)

    def on_start(self):
        # Публичным API нужны настройки прокси/сертификатов окружения, если они заданы.
        self.client.trust_env = True

    @task
    def posts(self):
        with self.client.get('https://jsonplaceholder.typicode.com/posts', name='Public: /posts',
                             timeout=TIMEOUT, catch_response=True) as response:
            data = json_response(response)
            if data is not None and not (isinstance(data, list) and len(data) > 0 and
                all(isinstance(post, dict) and {'id', 'userId', 'title', 'body'} <= post.keys()
                    for post in data)):
                response.failure('Invalid posts list')

    @task
    def weather(self):
        with self.client.get('https://wttr.in/Novosibirsk?format=j1', name='Public: wttr.in/Novosibirsk',
                             timeout=TIMEOUT, catch_response=True) as response:
            data = json_response(response)
            if data is not None and not (isinstance(data, dict) and data.get('current_condition')
                                         and data.get('weather')):
                response.failure('Missing current_condition or weather')
