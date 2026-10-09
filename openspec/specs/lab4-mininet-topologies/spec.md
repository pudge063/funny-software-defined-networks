# lab4-mininet-topologies Specification

## Purpose

Лабораторная работа 4 «Создание топологий в Mininet»: пользовательские
топологии на Mininet Python API с параметрами каналов, их проверка `ping` и
`iperf`, а также автоматические тесты топологий на фикстурах и на реальных
Mininet + Floodlight.

Артефакты – таблица R1 (раздел Reference). Общие требования к стенду и обходы
дефектов Floodlight – `specs/sdn-lab-environment`.

## Requirements

### Requirement: Общий модуль common.py

`reports/lab4/topologies/common.py` SHALL предоставлять символы с
контрактами из таблицы R2. Сеть с внешним контроллером MUST собираться только
через `make_net()`.

#### Scenario: Сеть с внешним контроллером

- **WHEN** вызывается `make_net(topo, ControllerAddr(...), "OpenFlow13", host=..., link=...)`
- **THEN** коммутаторы – `OVSSwitch(protocols="OpenFlow13")`, контроллер
  `c0` – `RemoteController` с заданными ip/port
- **AND** IPv6 отключён до `net.start()`

#### Scenario: Сеть без внешнего контроллера

- **WHEN** вызывается `make_net(topo)` без `controller`
- **THEN** поведение идентично `Mininet(topo=topo, **kwargs)`, IPv6 не
  трогается

#### Scenario: Разбор адреса контроллера

- **WHEN** `parse_controller` получает `127.0.0.1`, `:6653`, `host:port`,
  `h:0` или `h:70000`
- **THEN** выбрасывается `argparse.ArgumentTypeError`
- **AND** `parse_controller("::1:6653") == ControllerAddr("::1", 6653)`

### Requirement: Линейная топология (LinearTopo.py)

`LinearTopo.build(k: int = 2)` SHALL создавать хосты `h1..hk` и коммутаторы
`s1..sk` в порядке: для каждого `i` – `addHost(h_i)`, `addSwitch(s_i)`,
`addLink(h_i, s_i)`, затем `addLink(s_i, s_{i-1})` при `i > 1`; атрибут
`self.k` MUST сохраняться. `simple_test(k=4, controller=None) -> float`
MUST возвращать процент потерь `pingAll`.

#### Scenario: Запуск скрипта

- **WHEN** выполняется `sudo ./LinearTopo.py`
- **THEN** создаются 4 хоста, 4 коммутатора и контроллер c0
- **AND** результат `0% dropped (12/12 received)`

### Requirement: Линейная топология с ограничениями (LinearTopoPerf.py)

`LinearTopo.build(k: int = 2, linkopts: LinkOpts | None = None)` SHALL
повторять порядок `LinearTopo.py`, задавая хостам `cpu=0.5 / k`, а всем
каналам – `linkopts` (по умолчанию `DEFAULT_LINKOPTS`, таблица R3).
`perf_test(k=4, linkopts=None, controller=None)` MUST использовать
`CPULimitedHost` и `TCLink` и возвращать `(потери pingAll, результат iperf)`.

#### Scenario: Запуск скрипта с потерями 1%

- **WHEN** выполняется `sudo ./LinearTopoPerf.py`
- **THEN** `pingAll` MAY терять пакеты (в отчёте `8% dropped (11/12)`)
- **AND** TCP h1–h4 существенно ниже 10 Мбит/с (в отчёте 1.6 Мбит/с) из-за
  потерь на 4 звеньях пути

### Requirement: Структура дерева (TreeTopo.py, задание 1)

`CustomTopo.build(linkopts1, linkopts2, linkopts3, fanout: int = 2)` SHALL
строить 1 core (`cs1`) → `k` aggregation (`as*`) → `k²` edge (`es*`) → `k³`
хостов (`h*`). `addLink` MUST вызываться как `(потомок, родитель)` с
`linkopts1` для `(as, cs)`, `linkopts2` для `(es, as)`, `linkopts3` для
`(h, es)`. Параметры каналов скрипта – таблица R4.

#### Scenario: k = 2

- **WHEN** выполняется `sudo ./TreeTopo.py --fanout 2`
- **THEN** 7 коммутаторов, 8 хостов, `0% dropped (56/56 received)`
- **AND** RTT h1–h8 ≈ 32.8 мс (расчётный 2 × (5+2+1+1+2+5) = 32 мс)
- **AND** iperf ≈ 9.5 Мбит/с (узкое место – edge–host 10 Мбит/с)

#### Scenario: k = 3

- **WHEN** выполняется `sudo ./TreeTopo.py --fanout 3`
- **THEN** 13 коммутаторов, 27 хостов, `0% dropped (702/702 received)`

### Requirement: DPID коммутаторов дерева

DPID коммутаторов дерева SHALL задаваться явно функцией
`dpid(prefix, number) -> str` (hex-строка): core `0x100`, aggregation
`0x200 + a`, edge `0x300 + e`. Без этого Mininet выводит одинаковый DPID из
цифр имён `cs1`, `as1`, `es1`.

#### Scenario: Уникальность DPID

- **WHEN** строится `CustomTopo(fanout=2)`
- **THEN** `cs1` → `"100"`, `as2` → `"202"`, `es4` → `"304"`
- **AND** все DPID различны

### Requirement: Интерфейс запуска дерева

`TreeTopo.py` SHALL принимать аргументы из таблицы R5 и предоставлять
`run(...) -> TreeResult(ping_loss: float, iperf: list[str])`. С
`--controller` скрипт MUST выполнить `waitConnected`, ожидание
`--discovery-time`, `announce_hosts` и только затем `pingAll`.

#### Scenario: Подключение к Floodlight

- **WHEN** выполняется `sudo ./TreeTopo.py --controller 127.0.0.1:6653`
- **THEN** сеть подключается к Floodlight по OpenFlow 1.3
- **AND** `pingAll` начинается не раньше чем через `--discovery-time` секунд

### Requirement: Структура кольца (RingTopo.py, задание 2)

`RingTopo.build(n: int = 3, k: int = 3, ringopts=None, hostopts=None)` SHALL
создавать коммутаторы `s1..sn`, к коммутатору `s_i` – хосты
`h_{(i-1)k+1}..h_{ik}` с `hostopts`, затем звенья `s_i – s_{i+1 mod n}` с
`ringopts`. При `n = 2` MUST создаваться одно звено `s1–s2`, при `n = 1` –
ни одного. Порядок вызовов MUST сохраняться: от него зависят номера портов в
отчёте.

#### Scenario: Кольцо как цикл

- **WHEN** строится `RingTopo(n=4, k=2)`
- **THEN** у каждого `s_i` ровно два соседа-коммутатора: `s_{i-1}` и `s_{i+1}`
  по модулю `n`

### Requirement: Режимы работы кольца

`make_ring_net(topo, controller, protocols)` SHALL поддерживать режимы из
таблицы R6. В режиме STP `wait_stp()` MUST опрашивать `status:stp_state`
портов OVS и завершаться, когда все порты в `forwarding`, `blocking` или
`disabled`. Аргументы CLI – таблица R7.

#### Scenario: Кольцо 3 × 3 под Floodlight

- **WHEN** выполняется `sudo ./RingTopo.py -n 3 -k 3 --ring-bw 20 --ring-delay 10ms --host-bw 10 --host-delay 1ms`
- **THEN** `0% dropped (72/72 received)`
- **AND** RTT h1–h2 ≈ 4.2 мс, h1–h4 ≈ 24.3 мс (расчётный 24 мс)
- **AND** iperf h1–h4 ≈ 9.5 Мбит/с

#### Scenario: Узкое звено кольца

- **WHEN** `--ring-bw 5 --ring-delay 20ms`
- **THEN** RTT h1–h4 ≈ 44.8 мс (расчётный 44 мс), iperf ≈ 4.8 Мбит/с

#### Scenario: Кольцо 4 × 2 со STP

- **WHEN** выполняется `sudo ./RingTopo.py -n 4 -k 2 --stp`
- **THEN** STP сходится, один порт кольца в состоянии `blocking`
- **AND** `0% dropped (56/56 received)`

#### Scenario: Кольцо без обхода петли

- **WHEN** кольцо запускается с learning-switch контроллером без STP
- **THEN** широковещательные ARP зацикливаются (broadcast storm); такой режим
  MUST NOT использоваться

### Requirement: Точка входа тестов

`make test` SHALL одной командой создать `.venv`, запустить `pytest` под
`sudo` и прогнать все тесты. Цели и переменные Makefile, переменные
окружения и конфигурация pytest MUST соответствовать таблице R8.

#### Scenario: Полный прогон на чистом стенде

- **WHEN** Floodlight не запущен и выполняется `make test`
- **THEN** результат – `108 passed` (91 unit + 17 integration), около 2.5 мин
- **AND** после завершения процесс Floodlight остановлен

#### Scenario: Только unit-тесты

- **WHEN** выполняется `make test-unit`
- **THEN** запускаются тесты без маркера `integration`, без `sudo`

### Requirement: Порядок и гейтинг тестов

Хук `pytest_collection_modifyitems` (`trylast=True`) SHALL упорядочивать
тесты по этапам: 0 – без маркера `integration`; 1 – integration без фикстуры
`floodlight`; 2 – integration с `floodlight`. Каждый тест MUST быть ограничен
300 с (`pytest-timeout`), поскольку `Mininet.iperf` бесконечно ждёт сервер
при нарушенной связности.

#### Scenario: Падение unit-теста

- **WHEN** падает тест из `tests/test_topologies.py`
- **THEN** все тесты с маркером `integration` получают статус `SKIPPED`

### Requirement: Unit-тесты на фикстурах

`tests/test_topologies.py` SHALL проверять топологии без root через фикстуры
`topo_case` / `topo`, параметризованные `TOPO_CASES` (таблица R9). Каждый
`TopoCase` MUST задавать ожидаемые `hosts`, `switches`, `links`,
`switch_links`; для каждого случая MUST выполняться структурные проверки
из таблицы R9.

#### Scenario: Добавление новой топологии

- **WHEN** в `reports/lab4/topologies/` добавляется топология
- **THEN** в `TOPO_CASES` добавляется хотя бы один `TopoCase` с ожидаемыми
  числами
- **AND** структурные проверки R9 проходят без изменения тестов

### Requirement: Integration-тесты без Floodlight

`tests/test_integration.py` SHALL содержать `test_linear_script_default_controller`
(`simple_test(k=4) == 0`) и `test_ring_stp_without_controller` (кольцо 4 × 2:
STP сошёлся, есть порт `blocking`, `pingAll == 0`).

#### Scenario: Порт 6653 занят

- **WHEN** на 6653 уже слушает Floodlight
- **THEN** `test_linear_script_default_controller` получает `SKIPPED`

### Requirement: Integration-тесты с Floodlight

Для каждого случая `FLOODLIGHT_CASES` (`linear-k4`, `linear-perf-k4` с
`linkopts={"bw": 10.0, "delay": "5ms"}`, `tree-k2`, `ring-n2-k2`,
`ring-n3-k3`) SHALL создаваться одна сеть (фикстура `floodlight_net`,
`scope="module"`), на которой выполняются `test_floodlight_sees_topology`,
`test_ping_all` и `test_iperf_limited_by_bottleneck`.

#### Scenario: Подготовка сети

- **WHEN** фикстура `floodlight_net` поднимает сеть
- **THEN** выполняются `cleanup()`, `floodlight.reset()`, `make_net`,
  `waitConnected(timeout=30)`, ожидание всех DPID в REST (30 с), ожидание
  точного совпадения связей (90 с), `announce_hosts`
- **AND** в teardown выполняются `net.stop()` и `cleanup()`

#### Scenario: Проверка топологии через REST

- **WHEN** сеть `ring-n3-k3` подключена к Floodlight
- **THEN** `/wm/topology/links/json` даёт ровно 3 неупорядоченные пары DPID
  `00:00:00:00:00:00:00:0X`

#### Scenario: Связность и пропускная способность

- **WHEN** выполняются `test_ping_all` и `test_iperf_limited_by_bottleneck`
- **THEN** `pingAll(timeout="1") == 0`
- **AND** обе стороны iperf в диапазоне `(0.5·bw_min, 1.05·bw_min]`, где
  `bw_min` – минимальный `bw` среди каналов; при отсутствии `bw` – `> 0`

### Requirement: Соответствие отчёта коду

Фрагменты кода в `reports/lab4/report.md` MUST совпадать с текущим кодом
`reports/lab4/topologies/`. Изменение порядка `addHost`/`addSwitch`/`addLink`
MUST сопровождаться перепроверкой выводов `dumpNodeConnections` в отчёте.

#### Scenario: Изменение кода топологии

- **WHEN** меняется класс топологии
- **THEN** обновляется соответствующий фрагмент в `report.md`
- **AND** `make test` проходит

## Reference

### R1. Артефакты

| Путь                                        | Назначение                                    |
| ------------------------------------------- | --------------------------------------------- |
| `reports/lab4/report.md`                    | отчёт, команды, результаты, фрагменты кода    |
| `reports/lab4/topologies/common.py`         | типы и сборка сети с внешним контроллером     |
| `reports/lab4/topologies/LinearTopo.py`     | линейная топология из методички               |
| `reports/lab4/topologies/LinearTopoPerf.py` | линейная с `CPULimitedHost` и `TCLink`        |
| `reports/lab4/topologies/TreeTopo.py`       | задание 1: дерево core/aggregation/edge/host  |
| `reports/lab4/topologies/RingTopo.py`       | задание 2: кольцо коммутаторов                |
| `tests/conftest.py`                         | фикстуры, клиент Floodlight, порядок тестов   |
| `tests/test_topologies.py`                  | unit-тесты (без root)                         |
| `tests/test_integration.py`                 | integration-тесты (root, Mininet, Floodlight) |
| `Makefile`                                  | точка входа `make test`                       |

### R2. API common.py

| Символ               | Контракт                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `LinkOpts`           | `TypedDict(total=False)`: `bw: float`, `delay: str`, `jitter: str`, `loss: float`, `max_queue_size: int`, `use_htb: bool` |
| `ControllerAddr`     | `NamedTuple(ip: str, port: int)`, `str()` → `"ip:port"`                                                                   |
| `DEFAULT_CONTROLLER` | `ControllerAddr("127.0.0.1", 6653)`                                                                                       |
| `OPENFLOW_VERSIONS`  | `("OpenFlow10", "OpenFlow13")`                                                                                            |
| `DEFAULT_OPENFLOW`   | `"OpenFlow13"`                                                                                                            |
| `parse_controller()` | argparse-тип `ip:port` → `ControllerAddr`; порт 1..65535; разбор по `rpartition(":")`                                     |
| `positive_int()`     | argparse-тип: целое ≥ 1                                                                                                   |
| `make_net()`         | `controller=None` → `Mininet(topo, **kwargs)` с c0; иначе `OVSSwitch(protocols)` + `RemoteController` + `disable_ipv6`    |
| `disable_ipv6()`     | `disable_ipv6=1` на хостах (`all`, `default`) и на каждом порту коммутаторов                                              |
| `announce_hosts()`   | каждый хост: `ping -c 1 -W 1 -b <broadcast своей подсети>`                                                                |

### R3. DEFAULT_LINKOPTS (LinearTopoPerf.py)

| Ключ             | Значение |
| ---------------- | -------- |
| `bw`             | `10.0`   |
| `delay`          | `"5ms"`  |
| `loss`           | `1.0`    |
| `max_queue_size` | `1000`   |
| `use_htb`        | `True`   |

### R4. Параметры каналов дерева

| Уровень            | Константа              | bw, Мбит/с | delay |
| ------------------ | ---------------------- | ---------- | ----- |
| core – aggregation | `CORE_LINKOPTS`        | 100        | 1ms   |
| aggregation – edge | `AGGREGATION_LINKOPTS` | 50         | 2ms   |
| edge – host        | `EDGE_LINKOPTS`        | 10         | 5ms   |

### R5. CLI TreeTopo.py

| Аргумент           | Тип / значения                 | По умолчанию                   |
| ------------------ | ------------------------------ | ------------------------------ |
| `-k`, `--fanout`   | `positive_int`                 | `2`                            |
| `--controller`     | `ip:port` (`parse_controller`) | нет – контроллер Mininet c0    |
| `--discovery-time` | float, секунды                 | `20.0` (только с контроллером) |
| `--protocols`      | `OpenFlow10` \| `OpenFlow13`   | `OpenFlow13`                   |
| `--cli`            | флаг                           | выкл.                          |

### R6. Режимы кольца

| Режим      | Коммутаторы                                  | Обход петли                           | Ожидание                                   |
| ---------- | -------------------------------------------- | ------------------------------------- | ------------------------------------------ |
| Floodlight | `OVSSwitch(protocols)` + `RemoteController`  | контроллер флудит по остовному дереву | `--discovery-time`, затем `announce_hosts` |
| `--stp`    | `OVSSwitch(failMode="standalone", stp=True)` | STP блокирует порт кольца             | `wait_stp()`, до 60 с                      |

### R7. CLI RingTopo.py

| Аргумент           | Тип / значения               | По умолчанию     |
| ------------------ | ---------------------------- | ---------------- |
| `-n`, `--switches` | `positive_int`               | `3`              |
| `-k`, `--fanout`   | `positive_int`               | `3`              |
| `--ring-bw`        | float, Мбит/с                | `20.0`           |
| `--ring-delay`     | str                          | `10ms`           |
| `--host-bw`        | float, Мбит/с                | `10.0`           |
| `--host-delay`     | str                          | `1ms`            |
| `--controller`     | `ip:port`                    | `127.0.0.1:6653` |
| `--discovery-time` | float, секунды               | `20.0`           |
| `--protocols`      | `OpenFlow10` \| `OpenFlow13` | `OpenFlow13`     |
| `--stp`            | флаг                         | выкл.            |
| `--cli`            | флаг                         | выкл.            |

### R8. Запуск тестов

| Элемент                   | Значение                                                      |
| ------------------------- | ------------------------------------------------------------- |
| `make test`               | все тесты (unit → Mininet → Mininet + Floodlight), под `sudo` |
| `make test-unit`          | только unit, без `sudo`                                       |
| `make test-integration`   | только `-m integration`, под `sudo`                           |
| `make clean`              | `sudo mn -c`, удалить `.venv` и `.pytest_cache`               |
| Makefile `PYTHON`         | `/usr/bin/python3`                                            |
| Makefile `FLOODLIGHT_JAR` | `$(HOME)/floodlight/target/floodlight.jar`                    |
| Makefile `OPENFLOW`       | `OpenFlow13`                                                  |
| Makefile `PYTEST_ARGS`    | дополнительные аргументы pytest                               |
| env `FLOODLIGHT_HOST`     | `127.0.0.1`                                                   |
| env `FLOODLIGHT_REST`     | `http://127.0.0.1:8080`                                       |
| pytest `testpaths`        | `["tests"]`                                                   |
| pytest `pythonpath`       | `["reports/lab4/topologies", "tests"]`                        |
| pytest `markers`          | `integration`                                                 |
| pytest `timeout`          | `300`                                                         |
| sudo-запуск               | `-p no:cacheprovider`, `PATH` передаётся через `env`          |

### R9. Unit-тесты

`TOPO_CASES`: `linear-k1`, `linear-k4`, `linear-perf-k4`, `tree-k1`,
`tree-k2`, `tree-k3`, `ring-n1-k2`, `ring-n2-k2`, `ring-n3-k3`, `ring-n5-k1`.

Структурные проверки для каждого случая:

| Проверка             | Критерий                                                              |
| -------------------- | --------------------------------------------------------------------- |
| Число узлов и связей | равно `hosts`, `switches`, `links`, `switch_links`                    |
| Имена                | строки, уникальны                                                     |
| Uplink хоста         | ровно один, к коммутатору                                             |
| Связность            | граф связный (BFS)                                                    |
| Петли и дубли        | нет связей узла с собой и повторных пар                               |
| Типы `TCLink`        | по `LinkOpts`; `delay` ~ `^\d+(\.\d+)?(us\|ms\|s)$`; `0 ≤ loss ≤ 100` |
| DPID                 | явный – hex ≤ 16 символов; все DPID уникальны                         |

Дополнительные тесты: цепочка linear; `cpu` и `linkopts` perf; уровни и DPID
дерева; кольцо как цикл; разделение `ringopts`/`hostopts`;
`parse_controller`; `positive_int`.
