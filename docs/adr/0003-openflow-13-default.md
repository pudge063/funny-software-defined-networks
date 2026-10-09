# ADR-0003. OpenFlow 1.3 – версия протокола по умолчанию

- **Статус:** Accepted
- **Дата:** 2026-10-08
- **Спецификации:** `openspec/specs/sdn-lab-environment`,
  `openspec/specs/lab2-openflow-capture`

## Контекст

OVS 2.17 поддерживает OpenFlow 1.0–1.5, Floodlight 1.2 рекламирует OF 1.5 с
откатом на 1.0–1.4. Без явного указания версия согласуется по bitmap и может
отличаться между запусками и инструментами. Анализ трафика в lab 2 и lab 3
ведётся диссектором `openflow_v4` (OF 1.3), отчёты описывают OF 1.3.

При проверке OF 1.0 как способа обойти дефект `pkt_mark` (ADR-0004)
выяснилось, что модуль Forwarding Floodlight 1.2 при OF 1.0 падает с
`OFMatch does not support matching on field ovs_tcp_flags` и не ставит правила
для TCP: `iperf` зависает.

## Решение

- Коммутаторы под Floodlight MUST работать по OpenFlow 1.3:
  CLI – `--switch ovsk,protocols=OpenFlow13`, код – `common.make_net(...,
protocols="OpenFlow13")` (`DEFAULT_OPENFLOW`).
- Версия настраивается (`--protocols`, переменная `OPENFLOW` в `make test`),
  но `OpenFlow10` допустим только для сценариев без TCP.

## Последствия

- Захваты и отчёты однородны: везде OF 1.3.
- OF 1.3 открывает путь дефекту `pkt_mark` – он закрывается ADR-0004.
- Смена версии по умолчанию требует нового ADR и прогона `make test`.
