# Architecture Decision Records

Архитектурные решения стенда SDN и схемы взаимодействия компонентов. Формат и
правила ведения – [ADR-0001](./0001-record-architecture-decisions.md).

## Архитектура стенда

![Архитектура стенда](./diagrams/architecture.svg)

Роли компонентов – [ADR-0002](./0002-sdn-stand-architecture.md). Схемы всех
сценариев – [processes.md](./processes.md).

## Реестр решений

| ADR                                                 | Решение                                                       | Статус   | Дата       |
| --------------------------------------------------- | ------------------------------------------------------------- | -------- | ---------- |
| [0001](./0001-record-architecture-decisions.md)     | Фиксировать архитектурные решения в ADR                       | Accepted | 2026-10-09 |
| [0002](./0002-sdn-stand-architecture.md)            | Архитектура стенда: Mininet + Open vSwitch + Floodlight       | Accepted | 2026-10-08 |
| [0003](./0003-openflow-13-default.md)               | OpenFlow 1.3 – версия протокола по умолчанию                  | Accepted | 2026-10-08 |
| [0004](./0004-disable-ipv6-with-floodlight.md)      | Отключать IPv6 в сетях под Floodlight                         | Accepted | 2026-10-08 |
| [0005](./0005-announce-hosts.md)                    | Объявлять хосты контроллеру после старта сети                 | Accepted | 2026-10-08 |
| [0006](./0006-isolate-floodlight-state-in-tests.md) | Перезапускать Floodlight между топологиями в тестах           | Accepted | 2026-10-08 |
| [0007](./0007-test-harness.md)                      | Тестовый контур: pytest на системном Python, `make test`      | Accepted | 2026-10-08 |
| [0008](./0008-ring-loop-handling.md)                | Петли в кольце: Floodlight или STP с опросом сходимости       | Accepted | 2026-10-08 |
| [0009](./0009-modern-topology-code.md)              | Современный код топологий: `build()`, типизация, общий модуль | Accepted | 2026-10-08 |

## Схемы

| Файл                                                                           | Содержание                                   |
| ------------------------------------------------------------------------------ | -------------------------------------------- |
| [architecture](./diagrams/architecture.svg)                                    | общая архитектура стенда                     |
| [p01](./diagrams/p01-switch-connect.svg) … [p10](./diagrams/p10-stale-arp.svg) | сценарии, см. [processes.md](./processes.md) |

Исходники – `diagrams/*.mmd` (Mermaid), конфиг рендера –
`diagrams/mermaid.json`. После изменения исходника выполнить `make diagrams`
и закоммитить SVG вместе с `.mmd`.

## Новый ADR

1. Скопировать структуру существующего ADR, взять следующий номер.
2. Заполнить «Контекст / Решение / Последствия», указать связанные
   спецификации `openspec/specs/*` и процессы.
3. Добавить строку в реестр выше.
4. Если решение меняет требования – оформить change в `openspec/changes/`.
