# sdn-lab-environment Specification

## Purpose

Общая спецификация стенда, на котором выполняются все лабораторные работы:
состав ПО, способ запуска контроллера и эмулятора, сетевые соглашения,
структура репозитория, инструменты сборки и известные дефекты окружения с
обязательными обходами. Спецификации конкретных лаб (`lab1-*` … `lab4-*`)
опираются на этот документ и не дублируют его.

## Requirements

### Requirement: Состав стенда

Стенд SHALL состоять из Ubuntu 22.04 с установленными Mininet (системный
`/usr/bin/python3`), Open vSwitch 2.17, Floodlight v1.2 (Java 8) и
tshark/Wireshark. Версии компонентов MUST соответствовать таблице Tech Stack
в `openspec/project.md`; отклонение версии MUST фиксироваться в этой таблице.

#### Scenario: Проверка версий окружения

- **WHEN** агент начинает работу на стенде
- **THEN** `python3 -c "from mininet.net import VERSION; print(VERSION)"` под
  `/usr/bin/python3` выводит версию Mininet
- **AND** `ovs-vsctl --version` выводит Open vSwitch 2.17.x
- **AND** `java -version` выводит 1.8.x
- **AND** файл `~/floodlight/target/floodlight.jar` существует

### Requirement: Запуск Floodlight

Floodlight SHALL запускаться командой `java -jar target/floodlight.jar` из
корня репозитория `~/floodlight`. Запуск из другой директории MUST
сопровождаться ключом `-cf <абсолютный путь к floodlightdefault.properties>`.
Root-привилегии для Floodlight MUST NOT требоваться.

#### Scenario: Запуск из корня репозитория

- **WHEN** выполняется `cd ~/floodlight && java -jar target/floodlight.jar`
- **THEN** в логе появляется `Listening for OpenFlow switches on [0.0.0.0]:6653`
- **AND** `curl -s localhost:8080/wm/core/controller/switches/json` возвращает
  JSON-массив

#### Scenario: Запуск из чужой директории

- **WHEN** выполняется `java -jar ~/floodlight/target/floodlight.jar` из `~`
- **THEN** процесс завершается с ошибкой `Could not read config file: No such
file or directory: src/main/resources/floodlightdefault.properties`

### Requirement: Подключение Mininet к Floodlight

Сеть Mininet, управляемая Floodlight, SHALL использовать OVS-коммутаторы с
протоколом OpenFlow 1.3 и удалённый контроллер `127.0.0.1:6653`. Для CLI это
`--switch ovsk,protocols=OpenFlow13 --controller=remote,ip=127.0.0.1,port=6653`,
для Python API – `common.make_net(topo, ControllerAddr(...))`.

#### Scenario: Линейная сеть через CLI

- **WHEN** запущен Floodlight и выполнено
  `sudo mn --topo linear,4 --switch ovsk,protocols=OpenFlow13 --ipbase=10.0.0.0/8 --controller=remote,ip=127.0.0.1,port=6653`
- **THEN** `mininet> pingall` сообщает `0% dropped (12/12 received)`
- **AND** REST `/wm/core/controller/switches/json` содержит 4 коммутатора с
  `openFlowVersion` = `OF_13`

### Requirement: Обход дефекта pkt_mark в OF1.3 packet-in

При подключении к Floodlight по OpenFlow 1.3 IPv6 на хостах и на портах
коммутаторов MUST быть отключён до `net.start()`. Причина: ядро помечает
MLDv2-отчёты (icmp6 type 143) меткой `skb->mark = 0xd4`, OVS 2.17 передаёт её
в match `OFPT_PACKET_IN` как NXM-поле `pkt_mark` (typeLen `0x00014204`),
Floodlight 1.2 не может его разобрать и разрывает соединение с коммутатором.
Реализация – `common.disable_ipv6()`, вызывается из `common.make_net()`.

#### Scenario: IPv6 включён

- **WHEN** сеть подключена к Floodlight по OF1.3 без `disable_ipv6`
- **THEN** лог Floodlight содержит `OFParseError: Unknown value for
discriminator typeLen of class OFOxmVer13: 82436`
- **AND** коммутаторы периодически переподключаются (`Disconnected connection`)

#### Scenario: IPv6 отключён

- **WHEN** сеть собрана через `common.make_net()` с внешним контроллером
- **THEN** в логе Floodlight нет `OFParseError`

### Requirement: Объявление хостов контроллеру

После установления соединений с контроллером и обнаружения связей каждый хост
MUST отправить хотя бы один кадр в сеть (`common.announce_hosts()`:
широковещательный ping). Причина: в конфигурации по умолчанию
`Forwarding.flood-arp=NO` Floodlight не флудит ARP к известным ему IP, а
отправляет его в последнюю известную точку подключения; хосты без IPv6 сами
не генерируют трафик, и после смены сети ARP уходит в несуществующий порт.

#### Scenario: Повторный запуск сети на том же контроллере

- **WHEN** на работающем Floodlight последовательно запускаются две сети с
  одинаковыми IP хостов
- **AND** во второй сети вызван `announce_hosts`
- **THEN** `ping` между любыми хостами второй сети проходит

### Requirement: Изоляция состояния контроллера между топологиями

Автоматические тесты, которые сами запустили Floodlight, MUST перезапускать
его перед каждой новой топологией (`Floodlight.reset()` в `tests/conftest.py`).
Причина: при быстром переподключении коммутаторов с теми же DPID Floodlight
1.2 до 35 с хранит устаревшие связи и строит по ним маршруты. Внешний
(уже запущенный) Floodlight тесты MUST NOT перезапускать.

#### Scenario: Тесты запускают Floodlight сами

- **WHEN** `make test` запускается при свободном порте 6653
- **THEN** фикстура `floodlight` запускает контроллер, перезапускает его перед
  каждой топологией и останавливает в конце сессии

#### Scenario: Floodlight уже запущен

- **WHEN** REST API отвечает на `:8080` до старта тестов
- **THEN** тесты используют его без перезапуска
- **AND** тест с контроллером Mininet по умолчанию помечается `SKIPPED`

### Requirement: Версия OpenFlow для Floodlight

Версия OpenFlow по умолчанию SHALL быть `OpenFlow13`. `OpenFlow10` MAY
использоваться только для сценариев без TCP-трафика: модуль Forwarding
Floodlight 1.2 при OF1.0 падает с
`OFMatch does not support matching on field ovs_tcp_flags` и не ставит
правила для TCP (iperf зависает).

#### Scenario: iperf при OpenFlow10

- **WHEN** сеть подключена к Floodlight по OpenFlow10 и запускается `iperf`
- **THEN** TCP-соединение не устанавливается, в логе Floodlight –
  `UnsupportedOperationException ... ovs_tcp_flags`

### Requirement: Очистка Mininet

Перед запуском сети после аварийного завершения предыдущей MUST выполняться
`sudo mn -c` (или `mininet.clean.cleanup()`). Код, управляющий сетью, MUST
вызывать `net.stop()` в блоке `finally`.

#### Scenario: Остатки предыдущей сети

- **WHEN** предыдущий запуск завершился исключением без `net.stop()`
- **THEN** новый запуск падает с `RTNETLINK answers: File exists`
- **AND** после `sudo mn -c` запуск проходит

### Requirement: Структура репозитория

Репозиторий SHALL иметь структуру из таблицы R1 (раздел Reference); новые
артефакты MUST размещаться согласно ей.

#### Scenario: Добавление новой лабы

- **WHEN** добавляется лаба N
- **THEN** создаются `reports/labN/report.md` и `reports/labN/images/`
- **AND** в `README.md` (Labs reports) и `SUMMARY.md` добавляются ссылки
- **AND** создаётся спецификация `openspec/specs/labN-<slug>/spec.md` и
  строка в навигации `openspec/AGENTS.md`

### Requirement: Окружение Python для тестов

Тесты SHALL выполняться интерпретатором `.venv/bin/python`, созданным из
`/usr/bin/python3` с `--system-site-packages` и `--without-pip` (на стенде
нет `python3.10-venv`; pip берётся из системных пакетов). Запуск под `sudo`
MUST передавать `PATH` и отключать кеш pytest (`-p no:cacheprovider`), чтобы
`.pytest_cache` не создавался от root.

#### Scenario: Создание окружения

- **WHEN** выполняется `make venv` на чистом клоне
- **THEN** создаётся `.venv`, в него ставятся `pytest` и `pytest-timeout`
- **AND** `.venv/bin/python -c "import mininet.net, pytest"` завершается успешно

### Requirement: Известные дефекты документации установки

Следующие расхождения в `README.md` (Installation Docs) SHALL считаться
известными и MUST учитываться при воспроизведении установки:

- `git -C ~/mininet checkout -b 2.3.0` создаёт ветку `2.3.0` от текущего HEAD,
  а не переключается на тег; фактически установлен Mininet 2.3.1b4.
  Для тега нужно `git checkout -b 2.3.0 2.3.0`.
- `git -C ~/floodlight checkout -b v1.2` – аналогично, тег не применяется.
- `git -C ~/floodlight submodules update --init` – опечатка, правильно
  `submodule`.

#### Scenario: Воспроизведение установки по README

- **WHEN** агент воспроизводит установку по `README.md`
- **THEN** он применяет исправленные команды из этого требования

## Reference

### R1. Структура репозитория

| Путь                        | Содержимое                                                      |
| --------------------------- | --------------------------------------------------------------- |
| `README.md`                 | установка стенда, раздел Tests                                  |
| `SUMMARY.md`                | сводка по всем лабам                                            |
| `reports/labN/report.md`    | отчёт лабы N                                                    |
| `reports/labN/images/`      | скриншоты отчёта лабы N                                         |
| `reports/lab4/topologies/`  | исполняемые топологии и `common.py`                             |
| `tests/`                    | pytest: `conftest.py`, unit и integration                       |
| `Makefile`                  | `venv`, `test`, `test-unit`, `test-integration`, `clean`        |
| `pyproject.toml`, `uv.lock` | зависимости, конфиги ruff/mdformat/pytest                       |
| `openspec/`                 | спецификации для агентов                                        |
| `docs/adr/`                 | ADR, схемы архитектуры и процессов (`diagrams/*.mmd` → `*.svg`) |
