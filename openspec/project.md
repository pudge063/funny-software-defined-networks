# Project Context

## Purpose

Репозиторий `funny-software-defined-networks` содержит отчёты и артефакты
четырёх лабораторных работ по программно-конфигурируемым сетям (SDN):
развёртывание стенда Mininet + Open vSwitch + Floodlight, анализ протокола
OpenFlow 1.3, управление потоками через ACL контроллера и программное
построение топологий через Mininet Python API.

Репозиторий одновременно является:

- **учебным отчётом** – `reports/labN/report.md`, `SUMMARY.md`;
- **исполняемым кодом** – топологии lab 4 (`reports/lab4/topologies/*.py`);
- **тестовым контуром** – `tests/`, запуск одной командой `make test`.

## Tech Stack

| Компонент        | Версия на стенде                | Где используется             | Примечание                                   |
| ---------------- | ------------------------------- | ---------------------------- | -------------------------------------------- |
| ОС               | Ubuntu 22.04.5 LTS              | всё                          | ВМ в Proxmox: 8 vCPU, 8 ГБ RAM, 50 ГБ диск   |
| Mininet          | 2.3.1b4 (`mininet.net.VERSION`) | lab 1–4                      | установлен в системный `/usr/bin/python3`    |
| Open vSwitch     | 2.17.12                         | lab 1–4                      | kernel datapath                              |
| Floodlight       | v1.2 (`1.2-SNAPSHOT`)           | lab 1–4                      | `~/floodlight/target/floodlight.jar`         |
| Java             | OpenJDK 1.8.0                   | Floodlight                   | Java 8 обязательна для сборки и запуска      |
| Thrift           | 0.9.3                           | сборка Floodlight            | собирается из исходников                     |
| Python (Mininet) | 3.10.12 (`/usr/bin/python3`)    | lab 4, тесты                 | Mininet недоступен из других интерпретаторов |
| pytest           | ≥ 8 (+ pytest-timeout ≥ 2.3)    | `tests/`                     | ставится в `.venv` через `make venv`         |
| Wireshark/tshark | 4.6 (PPA wireshark-dev)         | lab 2, lab 3                 | захват `tcp port 6653`                       |
| uv               | любой актуальный                | управление dev-зависимостями | `uv.lock` в репозитории                      |

Сетевые порты стенда:

| Порт | Сервис                         |
| ---- | ------------------------------ |
| 6653 | OpenFlow (Floodlight)          |
| 8080 | REST API и web UI Floodlight   |
| 6655 | Jython debug server Floodlight |
| 6642 | Floodlight SyncManager (RPC)   |

## Project Conventions

### Code Style

- Python ≥ 3.10 (ограничение снизу задано системным интерпретатором Mininet):
  `from __future__ import annotations`, аннотации типов, f-строки, `range`
  вместо `mininet.util.irange`, `super().__init__()`.
- Топологии Mininet MUST переопределять `Topo.build()`, а не `__init__`.
- Параметры каналов MUST иметь тип `common.LinkOpts` (TypedDict): `bw: float`
  (Мбит/с), `delay: str` (`"5ms"`), `loss: float` (0..100),
  `max_queue_size: int`, `use_htb: bool`.
- DPID передаётся в Mininet строкой из hex-цифр (`f"{value:x}"`).
- Линтер и форматтер – ruff (конфиг в `pyproject.toml`, isort с
  `known-first-party` для модулей топологий и `conftest`).
- Комментарии и docstring – на русском, идентификаторы – на английском.

### Documentation Style

- Markdown форматируется `mdformat` (`wrap = 80`, `number = true`, конфиг в
  `pyproject.toml`).
- Отчёт лабы: `reports/labN/report.md`, изображения –
  `reports/labN/images/imageK.png` (сквозная нумерация внутри лабы).
- Добавление или изменение результатов лабы MUST сопровождаться обновлением
  `SUMMARY.md` (таблица и раздел лабы).
- Фрагменты кода в отчётах MUST совпадать с кодом в репозитории.

### Architecture Patterns

- Каждая топология lab 4 – самостоятельный исполняемый скрипт
  (`sudo ./X.py`) и одновременно импортируемый модуль: класс `Topo`,
  функция запуска (`simple_test`, `perf_test`, `run`), `main()` с argparse.
- Общий код – только `reports/lab4/topologies/common.py`; скрипты
  импортируют его как top-level модуль (директория скрипта в `sys.path`).
- Сеть с внешним контроллером собирается исключительно через
  `common.make_net()`; обход этой функции ломает обходы дефектов Floodlight
  (см. `specs/sdn-lab-environment`).

### Testing Strategy

- `make test` – единственная точка входа: создаёт `.venv`, запускает
  `pytest` под `sudo` и прогоняет три этапа (unit → Mininet → Mininet +
  Floodlight). Подробности – `specs/lab4-mininet-topologies`.
- Unit-тесты MUST NOT требовать root, сети или Floodlight.
- Integration-тесты помечены `@pytest.mark.integration`.
- Перед завершением любой правки кода lab 4 MUST проходить `make test`.

### Git Workflow

- Основная ветка – `master`. Работа ведётся в ветках `dev/LAB-00N` или
  тематических, слияние через pull request.
- Сообщения коммитов – `<type>: <subject>` (`feature: lab 4`,
  `reports: lab 2`).

## Domain Context

- **SDN**: разделение плоскости управления (контроллер Floodlight) и
  плоскости данных (OVS-коммутаторы в Mininet). Протокол между ними –
  OpenFlow 1.3 поверх TCP 6653.
- **Реактивная модель**: пакет без совпадения в таблице потоков → table-miss
  (`priority=0 actions=CONTROLLER`) → `OFPT_PACKET_IN` → контроллер отвечает
  `OFPT_PACKET_OUT` и устанавливает правила `OFPT_FLOW_MOD` (модуль
  Forwarding, priority 1, idle-timeout 5 с).
- **Проактивная модель**: модули вроде ACL ставят правила без `PACKET_IN`
  (priority 30000).
- **Топология** в Floodlight определяется через LLDP (модуль
  LinkDiscoveryManager); хосты – по первому пакету от них (DeviceManager).

## Important Constraints

- Mininet и OVS требуют root; любые сетевые эксперименты выполняются через
  `sudo`.
- Одновременно может работать только одна сеть Mininet; после аварийного
  завершения MUST выполняться `sudo mn -c`.
- Контроллер Mininet по умолчанию и Floodlight используют один порт 6653 и
  не могут работать одновременно.
- Floodlight MUST запускаться из корня репозитория `~/floodlight`
  (относительный путь к `src/main/resources/floodlightdefault.properties`)
  либо с явным `-cf <path>`.

## External Dependencies

- Mininet: <https://github.com/mininet/mininet>, установка
  `util/install.sh -a`.
- Floodlight: <https://github.com/floodlight/floodlight>, сборка `ant dist`
  (процедура с патчами Thrift – `README.md`, раздел Installation Docs).
- Thrift 0.9.3: <http://archive.apache.org/dist/thrift/0.9.3/>.
- libthrift 0.9.3 jar: Maven Central.
- Wireshark PPA: `ppa:wireshark-dev/stable`.
