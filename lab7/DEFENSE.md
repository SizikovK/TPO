# Демонстрация лабораторной №7 преподавателю

Все команды выполняются из каталога TPO. Нужны работающий Docker Desktop/Engine и существующий образ `investigation/romulus-20250902/image.static.mtd`. Образ прошивки и локальный пароль Jenkins исключены из Git.

## 1. Запуск Jenkins в Docker

```bash
cd /home/kathlyju/VSCODEEEEE/study/TPO
python3 lab7/setup_env.py
docker compose --env-file lab7/.env -f lab7/compose.yaml up -d --build
docker compose --env-file lab7/.env -f lab7/compose.yaml ps
```

Первичная сборка скачивает Jenkins, QEMU, Firefox, плагины и Python-пакеты. При повторной демонстрации используется кеш. Дождись готовности Jenkins:

```bash
python3 lab7/jenkins_api.py status
```

Если Jenkins ещё загружается, повтори status через несколько секунд.

Открой **http://localhost:18080**. Логин — `admin`, пароль находится в локальном файле `lab7/.env`, в поле `JENKINS_ADMIN_PASSWORD`. Файл не включается в репозиторий и отчёт.

## 2. Что показать в Jenkins

1. Задание **openbmc-ci**.
2. Configure: Pipeline script from SCM, Git, адрес `https://github.com/SizikovK/TPO.git`, ветка `main`, Script Path `lab7/Jenkinsfile`.
3. Нажми **Build with Parameters**, оставь параметры по умолчанию и запусти сборку.
4. Открой Console Output и наблюдай этапы: Prepare → QEMU OpenBMC → API tests → WebUI tests → Load test.
5. После завершения открой Test Result и Build Artifacts.

QEMU запускается самим Pipeline внутри контейнера. Отдельно `lab3/start-bmc.sh` для этой лабораторной запускать не нужно.

## 3. Запуск той же сборки командой

Если уже запустил сборку через интерфейс, эту команду повторно не выполняй: она создаёт ещё одну сборку.

```bash
python3 lab7/jenkins_api.py validate
python3 lab7/jenkins_api.py build
python3 lab7/jenkins_api.py watch
python3 lab7/jenkins_api.py collect
```

validate проверяет Groovy Jenkinsfile валидатором самого Jenkins. watch выводит ход выполнения, collect скачивает реальные отчёты и артефакты последней поставленной этим скриптом в очередь сборки. Для сборки, запущенной через интерфейс, укажи её номер:

```bash
python3 lab7/jenkins_api.py watch --number 1
python3 lab7/jenkins_api.py collect --number 1
```

Номер 1 замени номером выбранной сборки.

## 4. Что показать в коде

Открой `lab7/Jenkinsfile`:

- `agent any` и последовательные стадии.
- `pollSCM`: проверка обновлений GitHub каждые 15 минут; запуск новой сборки при изменениях после начального выполнения.
- `disableConcurrentBuilds`: две сборки не используют одновременно порты QEMU.
- `catchError`: ошибки тестов дают UNSTABLE и позволяют выполнить следующие проверки.
- `junit`: результаты API и Selenium доступны в Test Result.
- `archiveArtifacts`: отчёт каждого этапа сохраняется в Jenkins.
- `post { always }`: остановка QEMU и сохранение артефактов даже при ошибках.

В `lab7/ci.py` покажи запуск настоящего QEMU с `-snapshot`, ожидание HTTP 200, вызовы существующих тестов №4/5 и нагрузочного сценария №6. WebUI проверяется на свежем QEMU после API-тестов.

## 5. Объяснение результата

Зелёная сборка не является обязательным требованием методички. UNSTABLE означает, что Pipeline выполнен, но тесты обнаружили проблемы проверяемого OpenBMC. На текущем стенде ранее выявлены расхождения HTTP-кодов, недостижение питания On, отсутствие датчиков и записи ошибки авторизации в Event logs. Точный результат сборки смотри в отчёте и Jenkins Test Result; результаты не подменяются.

В нагрузочном этапе проверяется только OpenBMC, как требует лабораторная №7: 10 пользователей, 2 пользователя/с, 30 секунд. Публичные сервисы здесь не нагружаются.

## 6. Завершение демонстрации

После завершения сборки QEMU остановится автоматически. Чтобы остановить Jenkins, сохранив его задания и историю:

```bash
docker compose --env-file lab7/.env -f lab7/compose.yaml stop
```

Для повторного запуска:

```bash
docker compose --env-file lab7/.env -f lab7/compose.yaml up -d
```

GitHub: https://github.com/SizikovK/TPO/blob/main/lab7/Jenkinsfile.
