# Лабораторная работа № 1. Запуск OpenBMC с использованием QEMU

## Цель

Запустить OpenBMC в QEMU, проверить основные функции, удалённый доступ, журналы и потребление ресурсов.

## Подготовка и запуск

Работа выполнена в CachyOS вместо указанной в методичке Ubuntu 24.04. Использованы QEMU 11.1.1, плата `romulus-bmc`, 256 МиБ гостевой RAM и [образ Romulus из официального релиза 2.9.0](https://github.com/openbmc/openbmc/releases/tag/2.9.0). Внутри образа `/etc/os-release` сообщает `VERSION_ID=2.9.0-rc1-0-g835472cca`.

Установка QEMU:

```bash
sudo pacman -Syu --needed qemu-system-arm
```

Получение готового образа (распаковка не требуется):

```bash
mkdir -p lab1/romulus
curl -fL https://github.com/openbmc/openbmc/releases/download/2.9.0/obmc-phosphor-image-romulus.static.mtd \
  -o lab1/romulus/obmc-phosphor-image-romulus.static.mtd
```

Запуск из каталога `TPO`:

```bash
qemu-system-arm \
  -m 256 -M romulus-bmc -nographic \
  -drive file=lab1/romulus/obmc-phosphor-image-romulus.static.mtd,format=raw,if=mtd \
  -net nic \
  -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu
```

Вход в консоль: `root`, пароль `0penBmc`. Наличие оболочки и базовых утилит проверено командами `cat`, `sleep`, `ip`, `systemctl` и `journalctl`.

## Состояние и управление питанием

```console
root@romulus:~# obmcutil state
CurrentBMCState     : xyz.openbmc_project.State.BMC.BMCState.Ready
CurrentPowerState   : xyz.openbmc_project.State.Chassis.PowerState.Off
CurrentHostState    : xyz.openbmc_project.State.Host.HostState.Off
BootProgress        : xyz.openbmc_project.State.Boot.Progress.ProgressStages.Unspecified
OperatingSystemState: xyz.openbmc_project.State.OperatingSystem.Status.OSStatus.Inactive
```

BMC готов к работе (`Ready`), управляемый хост выключен (`Off`), его ОС неактивна.

Выполнены команды:

```bash
obmcutil poweron
sleep 10
obmcutil state
obmcutil poweroff
sleep 10
obmcutil state
```

Обе проверки состояния показали те же значения. Включение не подтверждено: журнал зафиксировал `Error: Write failed` в `avsbus-disable@0.service` и отказ зависимых целей запуска хоста. После `poweroff` хост остался выключенным; переход из On в Off не продемонстрирован.

## IPMI с другого хоста

Запрос выполнен со второго компьютера с Arch Linux к компьютеру с QEMU (`192.168.0.16`):

```console
❯ ipmitool -I lanplus -H 192.168.0.16 -p 2623 -U root -a fru print
Password:
FRU Device Description : Builtin FRU Device (ID 0)
 Device not present (Requested sensor, data, or record not found)

FRU Device Description : cpu0 (ID 1)
 Device not present (Unspecified error)

FRU Device Description : cpu1 (ID 2)
 Device not present (Unspecified error)

FRU Device Description : system (ID 3)
 Device not present (Unspecified error)

FRU Device Description : dimm0 (ID 4)
 Device not present (Unspecified error)

FRU Device Description : dimm1 (ID 5)
 Device not present (Unspecified error)

FRU Device Description : dimm2 (ID 6)
 Device not present (Unspecified error)

FRU Device Description : dimm3 (ID 7)
 Device not present (Unspecified error)

FRU Device Description : dimm4 (ID 8)
 Device not present (Unspecified error)

FRU Device Description : dimm5 (ID 9)
 Device not present (Unspecified error)

FRU Device Description : dimm6 (ID 10)
 Device not present (Unspecified error)

FRU Device Description : dimm7 (ID 11)
 Device not present (Unspecified error)

FRU Device Description : dimm8 (ID 12)
 Device not present (Unspecified error)

FRU Device Description : dimm9 (ID 13)
 Device not present (Unspecified error)

FRU Device Description : dimm10 (ID 14)
 Device not present (Unspecified error)

FRU Device Description : dimm11 (ID 15)
 Device not present (Unspecified error)

FRU Device Description : dimm12 (ID 16)
 Device not present (Unspecified error)

FRU Device Description : dimm13 (ID 17)
 Device not present (Unspecified error)

FRU Device Description : dimm14 (ID 18)
 Device not present (Unspecified error)

FRU Device Description : dimm15 (ID 19)
 Device not present (Unspecified error)

FRU Device Description : fan0 (ID 50)
 Device not present (Unspecified error)

FRU Device Description : fan1 (ID 51)
 Device not present (Unspecified error)

FRU Device Description : fan2 (ID 52)
 Device not present (Unspecified error)
```

Удалённая IPMI-сессия установлена, получен список FRU, но данные устройств недоступны. Сообщения `Device not present` не означают успешного чтения сведений о комплектующих.

## Redfish с другого хоста

На втором компьютере выполнено:

```bash
curl --noproxy '*' -k -i --connect-timeout 10 --max-time 30 \
  -u root https://192.168.0.16:2443/redfish/v1/Systems
```

Ответ (служебные HTTP-заголовки опущены):

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "@odata.id": "/redfish/v1/Systems",
  "@odata.type": "#ComputerSystemCollection.ComputerSystemCollection",
  "Members": [
    {
      "@odata.id": "/redfish/v1/Systems/system"
    }
  ],
  "Members@odata.count": 1,
  "Name": "Computer System Collection"
}
```

Получение базовой информации с отдельной машины подтверждено: HTTP 200, одна система.

## Журналы и документация

Выполнено:

```bash
journalctl -u xyz.openbmc_project.State.BMC.service --no-pager -n 30
```

Основные записи:

```text
Sep 25 12:53:17 romulus systemd[1]: Started Phosphor BMC State Manager.
Sep 25 12:53:46 romulus phosphor-bmc-state-manager[271]: BMC_READY
Sep 25 12:55:27 romulus phosphor-bmc-state-manager[271]: BMC_READY
Sep 25 12:55:29 romulus phosphor-bmc-state-manager[271]: Error in Unsubscribe
```

Менеджер состояний запущен, BMC перешёл в Ready. Причина `Error in Unsubscribe` по этим строкам не установлена; последующая проверка состояния также показала Ready.

Рассмотрены [документация OpenBMC](https://github.com/openbmc/docs), [управление хостом](https://github.com/openbmc/docs/blob/master/host-management.md) и [примеры Redfish](https://github.com/openbmc/docs/blob/master/REDFISH-cheatsheet.md): управление питанием, датчики, инвентаризация и события; BMC и управляемый хост имеют отдельные состояния.

## Потребление ресурсов QEMU

На хосте выполнены два замера — в простое и при командах `poweron`, `state`, `poweroff`:

```bash
top -b -d 2 -n 6 -p "$(pgrep -n -x qemu-system-arm)"
```

Первый снимок каждого запуска исключён, CPU усреднён по пяти оставшимся снимкам.

| Показатель процесса QEMU | Простой | Выполнение команд |
| --- | ---: | ---: |
| Средняя загрузка CPU | 21,50% | 76,22% |
| Диапазон CPU | 21,0–22,0% | 20,5–102,4% |
| Резидентная память (RES) | 601,50 МиБ | 602,11 МиБ |

Средняя процессорная нагрузка выросла примерно в 3,55 раза, память изменилась на 0,60 МиБ. Здесь 100% CPU соответствует одному логическому процессору; RES относится ко всему эмулятору, а не только к гостевой RAM.

## Вывод

OpenBMC запущен, консоль и BMC работают. IPMI и Redfish доступны с отдельного компьютера. Проверены команды управления питанием, журналы и ресурсы. Ограничения стенда: включение хоста завершилось ошибками, содержимое FRU недоступно.
