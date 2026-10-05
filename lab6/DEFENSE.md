# Демонстрация лабораторной №6 преподавателю

Команды выполняются на текущем компьютере. Виртуальное окружение и образ QEMU не загружаются в Git; после клонирования их нужно подготовить отдельно.

## Первый терминал: OpenBMC

```bash
cd /home/kathlyju/VSCODEEEEE/study/TPO
bash lab3/start-bmc.sh
```

Дождись загрузки, затем проверь готовность API во втором терминале. Если этот QEMU уже запущен, второй экземпляр не нужен.

## Второй терминал: доступность API

```bash
cd /home/kathlyju/VSCODEEEEE/study/TPO
curl --noproxy '*' -k -u root:0penBmc \
  -w '\nHTTP %{http_code}\n' https://127.0.0.1:3443/redfish/v1/
curl -sS -o /tmp/lab6-posts.json -w 'HTTP %{http_code}\n' \
  https://jsonplaceholder.typicode.com/posts
curl -sS -o /tmp/lab6-weather.json -w 'HTTP %{http_code}\n' \
  'https://wttr.in/Novosibirsk?format=j1'
```

При выполнении работы все три API вернули HTTP 200. Публичные сервисы требуют интернет и могут отвечать иначе в день защиты.

## Запуск веб-интерфейса Locust

```bash
lab6/.venv/bin/locust -f lab6/locustfile.py \
  --web-host 127.0.0.1 --web-port 8089 --class-picker \
  --csv lab6/results/demo --csv-full-history
```

Открой в браузере **http://localhost:8089**.

1. Выбери оба класса: `OpenBMCUser` и `PublicAPIUser`.
2. Введи Number of users: **10**.
3. Введи Ramp up: **2** пользователя/с.
4. Поле Host оставь пустым: адреса заданы в классах.
5. Нажми START, наблюдай Statistics и Charts около 40 секунд.
6. Нажми STOP. Покажи число запросов, ошибки, среднее время и p95.

10 — общее число пользователей, распределяемое между двумя классами. PowerState проверяется GET-запросом, питание нагрузочный тест не переключает.

## Что показать в коде

Открой `lab6/locustfile.py`:

- Два класса `HttpUser` и четыре метода `@task`.
- Для BMC — Basic Auth, самоподписанный TLS и паузы 1–3 с.
- Для публичных API — два разных адреса и паузы 3–5 с.
- `catch_response=True`: неверный HTTP-код или JSON считается ошибкой.
- Имена запросов разделяют системную информацию и PowerState в статистике.

Покажи `lab6/README.md`, CSV/HTML и графики `load-stages.png`, `load-history.png` в `lab6/results`.

## Повтор ступеней нагрузки (после остановки нагрузки в веб-интерфейсе)

```bash
lab6/.venv/bin/python lab6/run_load.py \
  --duration 40s --users 1 5 10 20 --public
lab6/.venv/bin/python lab6/analyze.py
```

Прогон занимает около четырёх минут. Максимальное испытанное число пользователей — не доказанный предел сервера. Критерий стабильной ступени в отчёте: запросы выполнены, HTTP/JSON ошибок нет; задержки оцениваются отдельно.

## Если нет окружения Python

```bash
python3 -m venv lab6/.venv
lab6/.venv/bin/python -m pip install -r lab6/requirements.txt
```

## Завершение

Во втором терминале останови Locust: **Ctrl+C**. В первом терминале заверши QEMU: **Ctrl+A, затем X**.

Репозиторий: https://github.com/SizikovK/TPO/tree/main/lab6.
