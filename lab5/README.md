# Лабораторная работа №5. Разработка автотестов для API Redfish с использованием PyTest

**Дата выполнения: 05.10.2026.**

## Цель работы

Освоить автоматизированное тестирование REST API OpenBMC: отправку HTTP-запросов, проверку ответов, управление сессией, контроль температуры CPU и сравнение показаний Redfish/IPMI.

## Стенд и файлы

Использован существующий учебный стенд: QEMU, romulus-bmc, 256 МиБ RAM, образ `investigation/romulus-20250902/image.static.mtd`. Запуск с `-snapshot` не сохраняет изменения в образ. Redfish: `https://127.0.0.1:3443`, IPMI: `127.0.0.1:3623`, пользователь `root`, учебный пароль `0penBmc`. Запросы выполнены локально. Проверка самоподписанного TLS-сертификата отключена, как в команде `curl -k` из задания.

Код всех пяти сценариев находится в [test_redfish.py](test_redfish.py), зависимости — в [requirements.txt](requirements.txt), настройки логирования — в [pytest.ini](pytest.ini). Фактические ответы и журналы сохранены в [results](results/).

## Часть 1. Настройка окружения

Все команды ниже выполняются из каталога `TPO`.

```bash
python3 -m venv --system-site-packages lab5/.venv
```

Вывод:

```text
(Вывод отсутствует; код завершения 0.)
```

Окружение использует системные пакеты; requests уже установлен в системе, pytest установлен в lab5/.venv. Первоначальная установка в ограниченном окружении не смогла подключиться к сети; повтор выполнен с разрешённым сетевым доступом. Ниже приведён вывод успешной установки.

```bash
lab5/.venv/bin/python -m pip install -r lab5/requirements.txt > lab5/results/install.txt 2>&1
cat lab5/results/install.txt
```

Вывод:

```text
Collecting pytest (from -r lab5/requirements.txt (line 1))
  Downloading pytest-9.1.1-py3-none-any.whl.metadata (7.6 kB)
Requirement already satisfied: requests in /usr/lib/python3.14/site-packages (from -r lab5/requirements.txt (line 2)) (2.34.2)
Collecting iniconfig>=1.0.1 (from pytest->-r lab5/requirements.txt (line 1))
  Using cached iniconfig-2.3.0-py3-none-any.whl.metadata (2.5 kB)
Requirement already satisfied: packaging>=22 in /usr/lib/python3.14/site-packages (from pytest->-r lab5/requirements.txt (line 1)) (26.3)
Requirement already satisfied: pluggy<2,>=1.5 in /usr/lib/python3.14/site-packages (from pytest->-r lab5/requirements.txt (line 1)) (1.6.0)
Requirement already satisfied: pygments>=2.7.2 in /usr/lib/python3.14/site-packages (from pytest->-r lab5/requirements.txt (line 1)) (2.21.0)
Requirement already satisfied: charset_normalizer<4,>=2 in /usr/lib/python3.14/site-packages (from requests->-r lab5/requirements.txt (line 2)) (3.5.1)
Requirement already satisfied: idna<4,>=2.5 in /usr/lib/python3.14/site-packages (from requests->-r lab5/requirements.txt (line 2)) (3.20)
Requirement already satisfied: urllib3<3,>=1.26 in /usr/lib/python3.14/site-packages (from requests->-r lab5/requirements.txt (line 2)) (2.7.0)
Requirement already satisfied: certifi>=2023.5.7 in /usr/lib/python3.14/site-packages (from requests->-r lab5/requirements.txt (line 2)) (2026.7.22)
Downloading pytest-9.1.1-py3-none-any.whl (386 kB)
Using cached iniconfig-2.3.0-py3-none-any.whl (7.5 kB)
Installing collected packages: iniconfig, pytest

Successfully installed iniconfig-2.3.0 pytest-9.1.1
```

```bash
lab5/.venv/bin/python --version
lab5/.venv/bin/python -m pip show pytest requests | rg '^(Name|Version):'
ipmitool -V
```

Вывод:

```text
Python 3.14.7
WARNING: The directory '/home/kathlyju/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
Name: pytest
Version: 9.1.1
Name: requests
Version: 2.34.2
ipmitool version 1.8.19.0.gsnapshot
```

### Запуск OpenBMC

При первом обращении к API сервер был выключен:

```bash
curl --noproxy '*' -k -sS --connect-timeout 5 -u root:0penBmc https://127.0.0.1:3443/redfish/v1/
```

Вывод:

```text
curl: (7) Failed to connect to 127.0.0.1:3443 after 0 ms: Could not connect to server
```

```bash
bash lab3/start-bmc.sh
```

Вывод:

```text
qemu-system-arm: warning: nic ftgmac100.1 has no peer

U-Boot 2019.04 (May 23 2025 - 06:46:26 +0000)
Model: Romulus BMC

Phosphor OpenBMC (Phosphor OpenBMC Project Reference Distro) nodistro.0 romulus ttyS4
romulus login:
```

Выше приведены фрагменты консольной загрузки; полный загрузочный вывод здесь не приводится. После загрузки проверена доступность API:

```bash
curl --noproxy '*' -k -sS --max-time 30 -u root:0penBmc -w '\nHTTP %{http_code}\n' https://127.0.0.1:3443/redfish/v1/ > lab5/results/service-root.txt
cat lab5/results/service-root.txt
```

Вывод:

```text
{
  "@odata.id": "/redfish/v1",
  "@odata.type": "#ServiceRoot.v1_15_0.ServiceRoot",
  "AccountService": {
    "@odata.id": "/redfish/v1/AccountService"
  },
  "Cables": {
    "@odata.id": "/redfish/v1/Cables"
  },
  "CertificateService": {
    "@odata.id": "/redfish/v1/CertificateService"
  },
  "Chassis": {
    "@odata.id": "/redfish/v1/Chassis"
  },
  "EventService": {
    "@odata.id": "/redfish/v1/EventService"
  },
  "Id": "RootService",
  "JsonSchemas": {
    "@odata.id": "/redfish/v1/JsonSchemas"
  },
  "Links": {
    "ManagerProvidingService": {
      "@odata.id": "/redfish/v1/Managers/bmc"
    },
    "Sessions": {
      "@odata.id": "/redfish/v1/SessionService/Sessions"
    }
  },
  "Managers": {
    "@odata.id": "/redfish/v1/Managers"
  },
  "Name": "Root Service",
  "ProtocolFeaturesSupported": {
    "DeepOperations": {
      "DeepPATCH": false,
      "DeepPOST": false
    },
    "ExcerptQuery": false,
    "ExpandQuery": {
      "ExpandAll": false,
      "Levels": false,
      "Links": false,
      "NoLinks": false
    },
    "FilterQuery": false,
    "OnlyMemberQuery": true,
    "SelectQuery": true
  },
  "RedfishVersion": "1.17.0",
  "Registries": {
    "@odata.id": "/redfish/v1/Registries"
  },
  "SessionService": {
    "@odata.id": "/redfish/v1/SessionService"
  },
  "Systems": {
    "@odata.id": "/redfish/v1/Systems"
  },
  "Tasks": {
    "@odata.id": "/redfish/v1/TaskService"
  },
  "TelemetryService": {
    "@odata.id": "/redfish/v1/TelemetryService"
  },
  "UUID": "922eb9d3-aaaf-41e6-911b-d49db81b52f5",
  "UpdateService": {
    "@odata.id": "/redfish/v1/UpdateService"
  }
}
HTTP 200
```

## Части 2–3. Реализация сценариев

1. `test_authentication`: POST `/redfish/v1/SessionService/Sessions`, проверка строго HTTP 200 по заданию и токена `X-Auth-Token`. Fixture предварительно проверяет наличие токена; фактическая сессия с HTTP 201 допускается для подготовки остальных тестов, но ожидание теста не изменено.
2. `test_system_information`: GET `/redfish/v1/Systems/system`, HTTP 200, наличие объекта `Status` и поля `PowerState`.
3. `test_power_on`: исходное состояние Off, POST `ComputerSystem.Reset` с `{"ResetType": "On"}`, проверка HTTP 202 и опрос состояния до On. Время ожидания — 60 секунд, интервал между запросами — 2 секунды. Время самого HTTP-запроса дополнительно ограничено 30 секундами. Сценарий реализует конкретное действие On из методички.
4. `test_cpu_temperature_normal`: поиск CPU в `Chassis → Thermal → Temperatures`, числовое конечное `ReadingCelsius`, `Status.Health=OK`, `Status.State=Enabled`, температура ниже `UpperThresholdNonCritical` и выше `LowerThresholdNonCritical`, если нижний порог задан. Единой произвольной нормы вроде 80 °C не вводится: предел берётся из датчика. Отсутствие датчика или верхнего порога означает Blocked.
5. `test_cpu_sensors_redfish_ipmi`: получение `ipmitool sensor list`, однозначное сопоставление имён, проверка единиц `degrees C`, состояния `ok`, числового значения и разницы с Redfish не больше допуска. По умолчанию допуск — 1 °C; это параметр учебной проверки, а не универсальная норма Redfish/IPMI. Для конкретного оборудования его нужно согласовать с точностью датчиков. Для разных имён предусмотрен `CPU_SENSOR_MAP` — JSON-словарь соответствий.

`pytest.fixture(scope='module')` переиспользует одну авторизованную сессию и удаляет её в финализаторе. Используется `X-Auth-Token`. Ошибки HTTP, JSON, запуска IPMI и тайм-ауты дают понятные сообщения. INFO-лог содержит методы, пути, HTTP-коды и состояние питания. Пароль и токен в журнал и файлы ответов сессии не записываются.

Основание температурной проверки — поля Thermal из [DMTF Redfish Data Model Specification](https://redfish.dmtf.org/schemas/v1/DSP0268_2025.2.pdf). Для IPMI использована [IPMI v2.0 Specification, SDR и Get Sensor Reading](https://www.intel.com/content/dam/www/public/us/en/documents/product-specifications/ipmi-v2-rev1-1-spec-errata-6-markup.pdf): ipmitool читает записи датчиков и преобразует показания в физические единицы. Реализация ориентирована на Thermal API данного образа; для оборудования, предоставляющего температуры только через современную коллекцию Sensors, потребуется адаптация обнаружения.

## Запуск тестов и полный вывод

```bash
lab5/.venv/bin/python -m pytest lab5/test_redfish.py -v -ra --tb=short --junitxml=lab5/results/assignment-check.xml > lab5/results/pytest-output.txt 2>&1
result=$?
cat lab5/results/pytest-output.txt
exit "$result"
```

Вывод:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- /home/kathlyju/VSCODEEEEE/study/TPO/lab5/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/kathlyju/VSCODEEEEE/study/TPO/lab5
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 5 items

lab5/test_redfish.py::test_authentication
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/SessionService/Sessions -> HTTP 201
FAILED                                                                   [ 20%]
lab5/test_redfish.py::test_system_information
-------------------------------- live log call ---------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:82 Status={'Health': 'OK', 'State': 'Disabled'}; PowerState=Off
PASSED                                                                   [ 40%]
lab5/test_redfish.py::test_power_on
-------------------------------- live log call ---------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/Systems/system/Actions/ComputerSystem.Reset -> HTTP 204
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:98 Включение: HTTP 204; состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'Off', 'PoweringOn', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'Off', 'Off']
FAILED                                                                   [ 60%]
lab5/test_redfish.py::test_cpu_temperature_normal
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis/Thermal -> HTTP 200
SKIPPED (Blocked: в Redfish Thermal нет датчиков температуры CPU)        [ 80%]
lab5/test_redfish.py::test_cpu_sensors_redfish_ipmi SKIPPED (Blocked...) [100%]
------------------------------ live log teardown -------------------------------
INFO     test_redfish:test_redfish.py:30 DELETE /redfish/v1/SessionService/Sessions/VhjQSmWHDj -> HTTP 200


=================================== FAILURES ===================================
_____________________________ test_authentication ______________________________
lab5/test_redfish.py:74: in test_authentication
    assert response.status_code == 200, f'По заданию HTTP 200, фактически {response.status_code}'
E   AssertionError: По заданию HTTP 200, фактически 201
E   assert 201 == 200
E    +  where 201 = <Response [201]>.status_code
------------------------------ Captured log setup ------------------------------
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/SessionService/Sessions -> HTTP 201
________________________________ test_power_on _________________________________
lab5/test_redfish.py:99: in test_power_on
    assert response.status_code == 202 and states[-1] == 'On', (
E   AssertionError: Ожидались HTTP 202 и PowerState=On; HTTP 204, состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'Off', 'PoweringOn', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'Off', 'Off']
E   assert (204 == 202)
E    +  where 204 = <Response [204]>.status_code
------------------------------ Captured log call -------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/Systems/system/Actions/ComputerSystem.Reset -> HTTP 204
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:98 Включение: HTTP 204; состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'Off', 'PoweringOn', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'Off', 'Off']
=============================== warnings summary ===============================
test_redfish.py::test_authentication
test_redfish.py::test_system_information
test_redfish.py::test_power_on
test_redfish.py::test_cpu_temperature_normal
test_redfish.py::test_cpu_sensors_redfish_ipmi
  /usr/lib/python3.14/site-packages/urllib3/connectionpool.py:1110: InsecureRequestWarning: Unverified HTTPS request is being made to host '127.0.0.1'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /home/kathlyju/VSCODEEEEE/study/TPO/lab5/results/assignment-check.xml -
=========================== short test summary info ============================
SKIPPED [1] lab5/test_redfish.py:125: Blocked: в Redfish Thermal нет датчиков температуры CPU
SKIPPED [1] lab5/test_redfish.py:141: Blocked: в Redfish Thermal нет датчиков температуры CPU
FAILED lab5/test_redfish.py::test_authentication - AssertionError: По заданию...
FAILED lab5/test_redfish.py::test_power_on - AssertionError: Ожидались HTTP 2...
======== 2 failed, 1 passed, 2 skipped, 5 warnings in 62.48s (0:01:02) =========
```

Код завершения pytest: **1**, поскольку два теста не пройдены. Предупреждения TLS отражают использование самоподписанного сертификата.

## Фактические данные датчиков

Ответ Thermal, сохранённый тестом:

```bash
cat lab5/results/GET_redfish_v1_Chassis_chassis_Thermal.txt
```

Вывод:

```text
HTTP 200
{
  "@odata.id": "/redfish/v1/Chassis/chassis/Thermal",
  "@odata.type": "#Thermal.v1_4_0.Thermal",
  "Fans": [],
  "Id": "Thermal",
  "Name": "Thermal",
  "Redundancy": [],
  "Temperatures": []
}
```

Независимо от пропуска теста сравнения выполнено чтение IPMI, чтобы проверить доступность его показаний:

```bash
IPMI_PASSWORD=0penBmc ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -E sensor list > lab5/results/ipmi-discovery.txt 2>&1
result=$?
cat lab5/results/ipmi-discovery.txt
echo "Exit code: $result"
```

Вывод:

```text
BootProgress     | 0x0        | discrete   | 0x0000| na        | na        | na        | na        | na        | na
occ0             | na         | discrete   | na    | na        | na        | na        | na        | na        | na
occ1             | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0             | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1             | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm0            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm1            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm2            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm3            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm4            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm5            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm6            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm7            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm8            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm9            | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm10           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm11           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm12           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm13           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm14           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm15           | na         | discrete   | na    | na        | na        | na        | na        | na        | na
dimm0_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm1_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm2_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm3_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm4_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm5_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm6_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm7_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm8_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm9_temp       | na         |            | na    | na        | na        | na        | na        | na        | na
dimm10_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
dimm11_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
dimm12_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
dimm13_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
dimm14_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
dimm15_temp      | na         |            | na    | na        | na        | na        | na        | na        | na
cpu0_core0       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core1       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core2       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core3       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core4       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core5       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core6       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core7       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core8       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core9       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core10      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core11      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core12      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core13      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core14      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core15      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core16      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core17      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core18      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core19      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core20      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core21      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core22      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu0_core23      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core0       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core1       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core2       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core3       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core4       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core5       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core6       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core7       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core8       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core9       | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core10      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core11      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core12      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core13      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core14      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core15      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core16      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core17      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core18      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core19      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core20      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core21      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core22      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
cpu1_core23      | na         | discrete   | na    | na        | na        | na        | na        | na        | na
p0_core0_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core1_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core2_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core3_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core4_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core5_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core6_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core7_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core8_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core9_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core10_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core11_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core12_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core13_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core14_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core15_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core16_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core17_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core18_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core19_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core20_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core21_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core22_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p0_core23_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core0_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core1_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core2_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core3_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core4_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core5_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core6_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core7_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core8_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core9_temp    | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core10_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core11_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core12_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core13_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core14_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core15_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core16_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core17_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core18_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core19_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core20_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core21_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core22_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
p1_core23_temp   | na         |            | na    | na        | na        | na        | na        | na        | na
AttemptsLeft     | 0x0        | discrete   | 0x0100| na        | na        | na        | na        | na        | na
OperatingSystemS | 0x0        | discrete   | 0x0000| na        | na        | na        | na        | na        | na

Exit code: 0
```

`na` означает недоступное показание. Дискретные записи cpu0/cpu1 и отсутствующие значения p0_core*_temp/p1_core*_temp не подтверждают измеренную температуру.

## Результаты

| Сценарий | Ожидание задания | Фактический результат | Статус |
| --- | --- | --- | --- |
| Аутентификация | HTTP 200, токен | HTTP 201, токен получен и использован остальными тестами | Failed по HTTP-коду задания |
| Информация о системе | HTTP 200, Status и PowerState | HTTP 200, Status присутствует, исходно PowerState=Off | Passed |
| Включение | HTTP 202, переход в On | HTTP 204; Off → PoweringOn → PoweringOff → Off; On за время проверки не достигнуто | Failed |
| Температура CPU в норме | Числовая температура в пределах порогов | Датчики CPU в Thermal отсутствуют | Skipped / Blocked |
| CPU: Redfish/IPMI | Соответствующие датчики и показания в допуске | В Redfish датчиков нет; в отдельном IPMI-запросе показания na | Skipped / Blocked |

HTTP 201 создания сессии соответствует примеру стандарта [DMTF Redfish Specification, Session login](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.23.0.pdf). Поэтому падение первого теста отражает расхождение методички со стандартным ответом, а не отказ входа. Ожидание HTTP 200 намеренно сохранено согласно заданию. Принятие запроса питания с HTTP 204 также само по себе не подтверждает достижение On; проверка состояния это выявила.

## Ссылка на GitHub — обязательный пункт задания

Реализованные тесты и материалы лабораторной: [SizikovK/TPO — lab5](https://github.com/SizikovK/TPO/tree/main/lab5).

Код тестов: [test_redfish.py](https://github.com/SizikovK/TPO/blob/main/lab5/test_redfish.py).

## Вывод

Разработаны и выполнены пять автотестов в test_redfish.py с fixture, обработкой ошибок и логированием. Получение информации о системе подтверждено. Строгие проверки HTTP-кодов выявили расхождение фактических ответов с методичкой; переход питания в On не подтверждён. Проверки температуры и согласованности показаний реализованы, но выполнение заблокировано отсутствием данных CPU на стенде. Итог: **2 failed, 1 passed, 2 skipped**. Для полноценной проверки датчиков необходим стенд с доступными показаниями CPU. Ссылка на директорию с тестами приведена выше.

## Повторная проверка 05.10.2026

После проверки кода обнаружены и исправлены два недочёта: данные CPU читаются отдельно перед каждым температурным тестом; отсутствие верхнего порога одного датчика больше не прерывает проверку остальных датчиков. Локальная проверка логики подтвердила обнаружение перегрева второго CPU при отсутствующем пороге первого и статус Blocked при отсутствии порогов. Это проверка логики на заданных данных, а не измерение реального CPU.

Повторный прогон на свежем QEMU:

```bash
lab5/.venv/bin/python -m pytest lab5/test_redfish.py -v -ra --tb=short \
  -o log_file=lab5/results/recheck.log \
  --junitxml=lab5/results/recheck.xml > lab5/results/recheck-output.txt 2>&1
```

Полный вывод:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- /home/kathlyju/VSCODEEEEE/study/TPO/lab5/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/kathlyju/VSCODEEEEE/study/TPO/lab5
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 5 items

lab5/test_redfish.py::test_authentication
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/SessionService/Sessions -> HTTP 201
FAILED                                                                   [ 20%]
lab5/test_redfish.py::test_system_information
-------------------------------- live log call ---------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:82 Status={'Health': 'OK', 'State': 'Disabled'}; PowerState=Off
PASSED                                                                   [ 40%]
lab5/test_redfish.py::test_power_on
-------------------------------- live log call ---------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/Systems/system/Actions/ComputerSystem.Reset -> HTTP 204
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:98 Включение: HTTP 204; состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'PoweringOff', 'Off', 'Off', 'Off']
FAILED                                                                   [ 60%]
lab5/test_redfish.py::test_cpu_temperature_normal
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis/Thermal -> HTTP 200
SKIPPED (Blocked: в Redfish Thermal нет датчиков температуры CPU)        [ 80%]
lab5/test_redfish.py::test_cpu_sensors_redfish_ipmi
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Chassis/chassis/Thermal -> HTTP 200
SKIPPED (Blocked: в Redfish Thermal нет датчиков температуры CPU)        [100%]
------------------------------ live log teardown -------------------------------
INFO     test_redfish:test_redfish.py:30 DELETE /redfish/v1/SessionService/Sessions/K4kII7nbHn -> HTTP 200


=================================== FAILURES ===================================
_____________________________ test_authentication ______________________________
lab5/test_redfish.py:74: in test_authentication
    assert response.status_code == 200, f'По заданию HTTP 200, фактически {response.status_code}'
E   AssertionError: По заданию HTTP 200, фактически 201
E   assert 201 == 200
E    +  where 201 = <Response [201]>.status_code
------------------------------ Captured log setup ------------------------------
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/SessionService/Sessions -> HTTP 201
________________________________ test_power_on _________________________________
lab5/test_redfish.py:99: in test_power_on
    assert response.status_code == 202 and states[-1] == 'On', (
E   AssertionError: Ожидались HTTP 202 и PowerState=On; HTTP 204, состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'PoweringOff', 'Off', 'Off', 'Off']
E   assert (204 == 202)
E    +  where 204 = <Response [204]>.status_code
------------------------------ Captured log call -------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/Systems/system/Actions/ComputerSystem.Reset -> HTTP 204
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:98 Включение: HTTP 204; состояния=['Off', 'PoweringOn', 'PoweringOff', 'PoweringOff', 'Off', 'Off', 'Off', 'PoweringOn', 'Off', 'Off', 'Off', 'Off', 'PoweringOff', 'Off', 'Off', 'Off']
=============================== warnings summary ===============================
test_redfish.py::test_authentication
test_redfish.py::test_system_information
test_redfish.py::test_power_on
test_redfish.py::test_cpu_temperature_normal
test_redfish.py::test_cpu_sensors_redfish_ipmi
  /usr/lib/python3.14/site-packages/urllib3/connectionpool.py:1110: InsecureRequestWarning: Unverified HTTPS request is being made to host '127.0.0.1'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /home/kathlyju/VSCODEEEEE/study/TPO/lab5/results/recheck.xml -
=========================== short test summary info ============================
SKIPPED [1] lab5/test_redfish.py:125: Blocked: в Redfish Thermal нет датчиков температуры CPU
SKIPPED [1] lab5/test_redfish.py:145: Blocked: в Redfish Thermal нет датчиков температуры CPU
FAILED lab5/test_redfish.py::test_authentication - AssertionError: По заданию...
FAILED lab5/test_redfish.py::test_power_on - AssertionError: Ожидались HTTP 2...
======== 2 failed, 1 passed, 2 skipped, 5 warnings in 63.35s (0:01:03) =========
```

Код завершения: 1. Результат прежний: 2 failed, 1 passed, 2 skipped. Отдельная команда для короткой защиты также проверена:

```bash
lab5/.venv/bin/python -m pytest lab5/test_redfish.py -v -k test_system_information \
  -o log_file=/tmp/lab5-short-recheck.log > lab5/results/short-recheck-output.txt 2>&1
```

Полный вывод:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- /home/kathlyju/VSCODEEEEE/study/TPO/lab5/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/kathlyju/VSCODEEEEE/study/TPO/lab5
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 5 items / 4 deselected / 1 selected

lab5/test_redfish.py::test_system_information
-------------------------------- live log setup --------------------------------
INFO     test_redfish:test_redfish.py:30 POST /redfish/v1/SessionService/Sessions -> HTTP 201
-------------------------------- live log call ---------------------------------
INFO     test_redfish:test_redfish.py:30 GET /redfish/v1/Systems/system -> HTTP 200
INFO     test_redfish:test_redfish.py:82 Status={'Health': 'OK', 'State': 'Disabled'}; PowerState=PoweringOff
PASSED                                                                   [100%]
------------------------------ live log teardown -------------------------------
INFO     test_redfish:test_redfish.py:30 DELETE /redfish/v1/SessionService/Sessions/Rzl31MYwjW -> HTTP 200


=============================== warnings summary ===============================
test_redfish.py::test_system_information
  /usr/lib/python3.14/site-packages/urllib3/connectionpool.py:1110: InsecureRequestWarning: Unverified HTTPS request is being made to host '127.0.0.1'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 1 passed, 4 deselected, 1 warning in 2.56s ==================
```

Код завершения: 0. Синтаксис Python, shell-скрипта запуска и `git diff --check` проверены без ошибок. Команды защиты находятся отдельно в [DEFENSE.md](DEFENSE.md).
