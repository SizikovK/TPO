# Причина Off / Inactive: контрольный опыт 26.09.2026

Диагностика отдельно от отчётов лабораторных. Рабочий стенд не изменялся.

## Вывод

Непосредственная причина ошибок `avsbus-disable.sh` — отсутствие виртуальных I²C-регуляторов по адресам 0x70 и 0x73 на шинах 4 и 5 стандартной модели `romulus-bmc`. Это подтверждено деревом устройств и контрольным опытом на той же CachyOS, с тем же установленным QEMU и свежим образом.

После добавления адресатов все 14 записей проходят. Затем выявляется следующий барьер: отсутствует подтверждение питания `pgood`. Одного добавления регуляторов недостаточно для включения хоста, тем более загрузки его ОС.

## Проверка хостовой системы

- CachyOS, ядро `6.18.48-1-cachyos-lts`, x86_64; QEMU 11.1.1.
- Проверка `pacman -Qkk qemu-system-arm` вне песочницы: `16 total files, 0 altered files`.
- Начальная проверка внутри песочницы показывала несовпадение UID/GID; повторная проверка вне неё этих предупреждений не дала. Это не повреждение пакета.
- Ни ядро, ни пакеты, ни настройки безопасности хоста не изменялись.

## Контрольный опыт

Базовый запуск свежего образа описан в `PLAN.md`, журнал — `console.log`: AVS завершался с `status=1/FAILURE`.

Для диагностического запуска использованы тот же образ и QEMU, `-snapshot`, 256 МиБ RAM, без сетевого подключения (`-nic none`). Добавлены:

```text
-device isl69260,bus=aspeed.i2c.bus.4,address=0x70
-device isl69260,bus=aspeed.i2c.bus.4,address=0x73
-device isl69260,bus=aspeed.i2c.bus.5,address=0x70
-device isl69260,bus=aspeed.i2c.bus.5,address=0x73
```

ISL69260 здесь — диагностическая модель PMBus, а не утверждение о точном соответствии регуляторам реальной Romulus. Её показания напряжения/тока не являются измерениями настоящего оборудования.

В гостевой консоли:

```sh
sh -ex /usr/bin/avsbus-disable.sh; echo AVS_EXIT=$?
obmcutil poweron
sleep 10
systemctl status avsbus-disable@0.service vrm-control@0.service --no-pager -l
obmcutil state
busctl introspect org.openbmc.control.Power /org/openbmc/control/power0
journalctl -b -u org.openbmc.control.Power@0.service --no-pager -n 35
```

`sh -e` прерывает скрипт при ошибке; в трассировке выполнены все 14 команд, результат `AVS_EXIT=0`. После запроса включения обе службы завершились с `status=0/SUCCESS`.

Дальнейший результат:

```text
CurrentBMCState     : xyz.openbmc_project.State.BMC.BMCState.Ready
CurrentPowerState   : xyz.openbmc_project.State.Chassis.PowerState.TransitioningToOn
CurrentHostState    : xyz.openbmc_project.State.Host.HostState.TransitioningToRunning
BootProgress        : xyz.openbmc_project.State.Boot.Progress.ProgressStages.Unspecified
OperatingSystemState: xyz.openbmc_project.State.OperatingSystem.Status.OSStatus.Inactive
```

Служба питания сообщает `state=1`, но `pgood=0`. Журнал:

```text
Power GPIO power good input: SYS_PWROK_BUFF
PowerControl: setting power up SOFTWARE_PGOOD to 1
PowerControl: setting power up BMC_POWER_UP to 1
ERROR PowerControl: Pgood poll timeout
```

`phosphor-wait-power-on@0.service` остаётся в состоянии запуска, зависимые цели ожидают его завершения. В новой версии это имя службы отличается от старого `op-wait-power-on@0.service`.

Полный журнал опыта: `console-vrm.log`. Тестовый QEMU завершён, снимок отброшен. SHA-256 исходного нового образа остался `b06d6218d2683ceb371b154e49cc32600f9148009c1cc0932f39735905517462`.

## Что означает Inactive и что исправлять

`OperatingSystemState` относится к ОС управляемого сервера, а не к CachyOS и не к Linux внутри BMC. Данная машина QEMU эмулирует BMC; самостоятельного управляемого POWER-сервера с загружаемой ОС в запуске нет. См. [документацию модели Aspeed](https://www.qemu.org/docs/master/system/arm/aspeed.html).

Для прохождения аппаратной последовательности нужна согласованная модель регуляторов, GPIO обратной связи питания и следующих устройств хоста. Для настоящего Active дополнительно нужен сам управляемый хост с загрузкой ОС и обменом с BMC. Подмена свойств состояния или игнорирование ошибок этих компонентов не создаёт.

Причина конкретного сбоя AVS установлена экспериментально; переустановка CachyOS для неё не обоснована. Этот опыт не устанавливает причину отдельной периодической ошибки сетевой IPMI-сессии.
