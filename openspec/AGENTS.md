# OpenSpec: инструкция для агентов

Этот файл – точка входа для любого агента, работающего с репозиторием. Он
описывает, где лежит каждая спецификация, что в ней искать, в каком порядке
читать и как вносить изменения.

## 1. Порядок чтения

1. `openspec/project.md` – контекст проекта: цель, стек и версии, порты,
   конвенции кода и документации, ограничения. Читается всегда.
2. `openspec/specs/sdn-lab-environment/spec.md` – стенд, запуск Floodlight и
   Mininet, дефекты окружения и обязательные обходы. Читается перед любой
   работой, которая запускает сеть или контроллер.
3. Спецификация конкретной лабы – по таблице навигации ниже.

## 2. Навигация по спецификациям

| Спецификация                                                         | Область                          | Искать здесь, если нужно…                                                                                                                                                                                      |
| -------------------------------------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`project.md`](./project.md)                                         | контекст проекта                 | версии ПО и портов; стиль кода и Markdown; структура тестов; git-конвенции; доменные термины                                                                                                                   |
| [`sdn-lab-environment`](./specs/sdn-lab-environment/spec.md)         | общий стенд                      | запустить Floodlight; подключить Mininet к контроллеру; понять `OFParseError`/переподключения; почему ARP не доходит; почему падает iperf на OF1.0; `mn -c`; структура репозитория; `.venv`; опечатки в README |
| [`lab1-sdn-testbed`](./specs/lab1-sdn-testbed/spec.md)               | lab 1, установка и первый запуск | установить Mininet; собрать Floodlight на Ubuntu 22.04 (Thrift 0.9.3, патчи); проверить handshake и UI                                                                                                         |
| [`lab2-openflow-capture`](./specs/lab2-openflow-capture/spec.md)     | lab 2, анализ OpenFlow           | захватить трафик `tshark`; порт и версия OpenFlow; смысл `PACKET_IN`/`PACKET_OUT`/`FLOW_MOD`/`ECHO`; действие `OFPAT_OUTPUT`                                                                                   |
| [`lab3-acl-flow-rules`](./specs/lab3-acl-flow-rules/spec.md)         | lab 3, ACL                       | создать правило ACL (UI/REST); ожидаемый `FLOW_MOD` priority 30000; `dump-flows`; `16% dropped`; фильтры tshark; приоритеты правил                                                                             |
| [`lab4-mininet-topologies`](./specs/lab4-mininet-topologies/spec.md) | lab 4, топологии и тесты         | API `common.py`; контракты `LinearTopo`/`LinearTopoPerf`/`CustomTopo`/`RingTopo`; CLI-флаги и умолчания; DPID; STP; ожидаемые RTT и iperf; `make test`; фикстуры и состав тестов                               |

### Быстрый поиск по задаче

| Задача                                                 | Документ → раздел                                                                             |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Запустить все тесты                                    | `lab4-mininet-topologies` → «Точка входа тестов»                                              |
| Добавить топологию                                     | `lab4-mininet-topologies` → «Unit-тесты на фикстурах», «Соответствие отчёта коду»             |
| Изменить сборку сети с Floodlight                      | `lab4-mininet-topologies` → «Общий модуль common.py»; `sdn-lab-environment` → обходы дефектов |
| Тест integration падает с потерей связности            | `sdn-lab-environment` → «Объявление хостов», «Изоляция состояния контроллера»                 |
| Floodlight не стартует (`Could not read config file`)  | `sdn-lab-environment` → «Запуск Floodlight»                                                   |
| Коммутаторы переподключаются, `OFParseError ... 82436` | `sdn-lab-environment` → «Обход дефекта pkt_mark»                                              |
| `RTNETLINK answers: File exists`                       | `sdn-lab-environment` → «Очистка Mininet»                                                     |
| Воспроизвести установку стенда                         | `lab1-sdn-testbed`; `sdn-lab-environment` → «Известные дефекты документации установки»        |
| Ответить на контрольные вопросы lab 2 / lab 3          | `lab2-openflow-capture`, `lab3-acl-flow-rules` → сценарии «Ответ на…» / таблицы               |
| Добавить новую лабу                                    | `sdn-lab-environment` → «Структура репозитория»                                               |
| Оформить Markdown                                      | `project.md` → Documentation Style                                                            |

## 3. Источники истины

При расхождении приоритет такой:

1. **Код и тесты** (`reports/lab4/topologies/`, `tests/`, `Makefile`,
   `pyproject.toml`) – для поведения lab 4.
2. **Спецификации** `openspec/specs/` – для требований и ожидаемых
   результатов.
3. **Отчёты** `reports/labN/report.md` – для зафиксированных измерений и
   выводов на момент выполнения лабы.
4. **`SUMMARY.md`, `README.md`** – производные документы.

Обнаруженное расхождение MUST устраняться в том же изменении: либо код
приводится к спецификации, либо спецификация обновляется через change
(раздел 5).

## 4. Правила для агентов

- Нормативные слова – по RFC 2119, на английском: MUST / MUST NOT / SHALL /
  SHOULD / MAY. Остальной текст спецификаций – на русском.
- Сетевые эксперименты требуют root; перед запуском сети проверять, что
  предыдущая остановлена (`sudo mn -c`).
- Не запускать контроллер Mininet по умолчанию при работающем Floodlight
  (общий порт 6653).
- Не запускать `pkill -f <шаблон>` с шаблоном, который входит в командную
  строку собственного шелла: процесс завершит сам себя. Использовать
  `pgrep -x java` или PID.
- Изменения кода lab 4 считаются завершёнными только после успешного
  `make test`; результат (`N passed`) указывается в отчёте об изменении.
- Не менять измерения в `reports/labN/report.md` без повторного выполнения
  эксперимента.
- Markdown после правок прогонять через `mdformat` (конфиг в
  `pyproject.toml`), Python – через `ruff check` и `ruff format`.

## 5. Процесс изменений (OpenSpec)

Изменение требований оформляется как change в `openspec/changes/<change-id>/`:

```
openspec/changes/<change-id>/
├── proposal.md          # Why / What Changes / Impact
├── tasks.md             # чек-лист реализации
├── design.md            # опционально: решения и компромиссы
└── specs/<capability>/spec.md   # дельты требований
```

- `<change-id>` – kebab-case, глагол в начале: `add-fat-tree-topology`,
  `update-floodlight-reset-policy`.
- Дельты оформляются секциями `## ADDED Requirements`,
  `## MODIFIED Requirements` (требование целиком, с новыми сценариями),
  `## REMOVED Requirements` (с причиной и миграцией),
  `## RENAMED Requirements`.
- Каждое требование MUST иметь хотя бы один `#### Scenario:` в формате
  `- **WHEN** …` / `- **THEN** …` (`- **AND** …` для продолжения).
- После реализации change переносится в `openspec/changes/archive/
YYYY-MM-DD-<change-id>/`, а дельты применяются к `openspec/specs/`.
- Проверка формата: `openspec validate --strict` (CLI
  `@fission-ai/openspec`), если установлен.

Change не требуется для: исправления опечаток, форматирования, обновления
версий в таблице Tech Stack без изменения поведения, правок отчётов без
изменения требований.
