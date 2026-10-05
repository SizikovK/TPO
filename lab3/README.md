# Лабораторная работа №3. Составление тест-плана тестирования OpenBMC

**Вариант 24. Проверка выполнена 03.10.2026.**

## Цель работы

Освоить составление тест-плана и разработать тест-кейсы проверки OpenBMC.

## Часть 1. Изучение OpenBMC

Рассмотрена [документация OpenBMC по управлению хостом](https://github.com/openbmc/docs/blob/master/host-management.md).

Основные функции OpenBMC: управление питанием сервера, мониторинг датчиков, удалённый доступ через IPMI/Redfish и регистрация событий.

## Часть 2. Разработка тест-плана

### 1. Цели тестирования

Проверить функции варианта 24 и сравнить фактические результаты с ожидаемыми.

### 2. Объём тестирования

| Группа | Тест-кейс |
| --- | --- |
| Управление питанием | TC3: перезагрузка сервера |
| Мониторинг | TC2: напряжение материнской платы |
| Удалённый доступ | TC1: подключение через IPMI |
| Логирование | TC2: запись логов при ошибке |

### 3. Подходы и методы

- Функциональное тестирование: проверка состояний, показаний и ответов команд.
- Интеграционное тестирование: проверка взаимодействия IPMI, служб OpenBMC и журнала.
- Тестирование безопасности: проверка отказа при неверном пароле.

### 4. Ресурсы

| Ресурс | Использованное средство |
| --- | --- |
| Компьютер | CachyOS |
| Эмулятор | QEMU 11.1.1, romulus-bmc, 256 МиБ RAM |
| Образ | OpenBMC 3.0.0-dev-734-gf330cd08ac из romulus.zip |
| Инструменты | ipmitool, obmcutil, journalctl, systemctl |
| IPMI | 127.0.0.1:3623 → порт 623 гостевой ОС |

### 5. График выполнения

| Этап | Плановое время |
| --- | --- |
| Подготовка стенда | 10 мин |
| Перезагрузка | 10 мин |
| Напряжение матплаты | 10 мин |
| IPMI | 5 мин |
| Логи при ошибке | 10 мин |
| Оформление отчёта | 10 мин |

### 6. Критерии начала и завершения

Начало: BMC готов, сеть настроена, инструменты установлены, тест-кейсы подготовлены. Для перезагрузки нужен включённый сервер с загруженной ОС, для напряжения — доступный датчик матплаты с известными пределами.

Успешное завершение: все тест-кейсы выполнены, ожидаемые результаты достигнуты, обнаруженные дефекты исправлены и повторно проверены.

## Часть 3. Выполнение тест-кейсов

Команды IPMI выполнены на компьютере с QEMU; команды obmcutil и journalctl — внутри OpenBMC.

### 1. Управление питанием — перезагрузка сервера

Проверка предусловия:

```bash
obmcutil state
```

Вывод:

```text
CurrentBMCState     : xyz.openbmc_project.State.BMC.BMCState.Ready
CurrentPowerState   : xyz.openbmc_project.State.Chassis.PowerState.Off
CurrentHostState    : xyz.openbmc_project.State.Host.HostState.Off
BootProgress        : xyz.openbmc_project.State.Boot.Progress.ProgressStages.Unspecified
OperatingSystemState: xyz.openbmc_project.State.OperatingSystem.Status.OSStatus.Inactive
```

Проверка питания через IPMI:

```bash
ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -P '0penBmc' chassis power status
```

Вывод:

```text
Chassis Power is off
```

Запланированная команда перезагрузки:

```bash
ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -P '0penBmc' chassis power reset
```

Команда reset не выполнена: хост выключен, его ОС не загружена. Проверка перезагрузки заблокирована.

### 2. Мониторинг — напряжение материнской платы

```bash
ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -P '0penBmc' sdr type Voltage
echo $?
```

Вывод первой команды пустой; код завершения:

```text
0
```

Датчик напряжения матплаты не найден. Проверка числового значения и допустимых пределов заблокирована.

### 3. Удалённый доступ — подключение через IPMI

Проверка с неверным паролем:

```bash
ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -P 'WrongLabPassword1' mc info
```

Вывод:

```text
Error: Unable to establish IPMI v2 / RMCP+ session
```

Код завершения — 1.

Проверка с правильным паролем:

```bash
ipmitool -I lanplus -H 127.0.0.1 -p 3623 -U root -P '0penBmc' mc info
```

Вывод:

```text
Device ID                 : 0
Device Revision           : 0
Firmware Revision         : 3.00
IPMI Version              : 2.0
Manufacturer ID           : 0
Manufacturer Name         : Unknown
Product ID                : 0 (0x0000)
Product Name              : Unknown (0x00)
Device Available          : yes
Provides Device SDRs      : yes
Additional Device Support :
    Sensor Device
    SEL Device
    FRU Inventory Device
    Chassis Device
Aux Firmware Rev Info     :
    0x00
    0x00
    0x00
    0x00
```

Код завершения — 0. IPMI-сессия устанавливается, неверный пароль отклоняется. Тест пройден.

### 4. Логирование — запись логов при ошибке

Сохранение позиции журнала и вызов ошибки включения:

```bash
cursor=$(journalctl -b -n 1 --show-cursor --no-pager | sed -n 's/^-- cursor: //p')
obmcutil poweron
sleep 30
journalctl -b --after-cursor="$cursor" -u avsbus-disable@0.service -u org.openbmc.control.Power@0.service --no-pager
```

Команда poweron завершилась с кодом 0. Фрагмент новых записей журнала:

```text
Oct 03 03:17:59 romulus systemd[1]: Starting Disable the AVS bus on the VRMs...
Oct 03 03:17:59 romulus avsbus-disable.sh[635]: Error: Write failed
Oct 03 03:17:59 romulus avsbus-disable.sh[636]: Error: Write failed
Oct 03 03:18:00 romulus systemd[1]: avsbus-disable@0.service: Main process exited, code=exited, status=1/FAILURE
Oct 03 03:18:00 romulus systemd[1]: avsbus-disable@0.service: Failed with result 'exit-code'.
Oct 03 03:18:00 romulus systemd[1]: Failed to start Disable the AVS bus on the VRMs.
```

Проверка служб:

```bash
systemctl --failed --no-pager
```

Фрагмент вывода:

```text
  UNIT                             LOAD   ACTIVE SUB    JOB   DESCRIPTION
* avsbus-disable@0.service         loaded failed failed start Disable the AVS bus on the VRMs
* avsbus-enable@0.service          loaded failed failed start Enable the AVS bus on VRMs
* phosphor-wait-power-on@0.service loaded failed failed start Wait for Power0 to turn on
* vrm-control@0.service            loaded failed failed start Apply voltage overrides to VRMs
```

Повторная проверка:

```bash
obmcutil state
```

Вывод:

```text
CurrentBMCState     : xyz.openbmc_project.State.BMC.BMCState.Ready
CurrentPowerState   : xyz.openbmc_project.State.Chassis.PowerState.Off
CurrentHostState    : xyz.openbmc_project.State.Host.HostState.TransitioningToRunning
BootProgress        : xyz.openbmc_project.State.Boot.Progress.ProgressStages.Unspecified
OperatingSystemState: xyz.openbmc_project.State.OperatingSystem.Status.OSStatus.Inactive
```

После попытки включения появилась новая запись с временем, службой и описанием ошибки; BMC остался Ready. Проверка регистрации ошибки пройдена.

## Часть 4. Таблица тест-кейсов

| ID | Название | Шаги выполнения | Ожидаемый результат | Фактический результат | Статус |
| --- | --- | --- | --- | --- | --- |
| PWR-03 | Перезагрузка сервера | Проверить питание; выполнить reset при включённом хосте; подтвердить повторную загрузку ОС. | Сервер перезагрузился, его ОС доступна. | Хост Off, ОС Inactive; reset не выполнялся. | Заблокирован |
| MON-02 | Напряжение матплаты | Получить Voltage-датчики; проверить значения и пределы. | Числовые значения в допустимом диапазоне. | Список Voltage пуст. | Заблокирован |
| REM-01 | Подключение через IPMI | Проверить неверный и правильный пароль, сведения BMC и питание. | Неверный пароль отклонён, правильный обеспечивает доступ. | Неверный пароль: код 1; правильный: код 0, IPMI 2.0, Firmware 3.00. | Пройден |
| LOG-02 | Логи при ошибке | Сохранить позицию журнала; вызвать ошибку; проверить новые записи. | Новая запись с временем и описанием ошибки. | В новых записях зафиксирован отказ avsbus-disable. | Пройден |

## Вывод

Составлен тест-план варианта 24: определены объём, методы, ресурсы, график, критерии начала и завершения, оформлена таблица тест-кейсов. Практически подтверждены подключение через IPMI и регистрация ошибки в журнале. Для выполнения кейсов перезагрузки и напряжения требуется стенд с включённым управляемым хостом и доступным датчиком напряжения.
