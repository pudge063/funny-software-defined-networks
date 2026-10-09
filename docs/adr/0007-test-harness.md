# ADR-0007. Тестовый контур: pytest на системном Python, запуск `make test`

- **Статус:** Accepted
- **Дата:** 2026-10-08
- **Спецификации:** `openspec/specs/lab4-mininet-topologies`
- **Процесс:** [P7](./processes.md#p7-make-test)

## Контекст

- Mininet установлен `install.sh` в системный `/usr/bin/python3` (3.10) и
  недоступен из других интерпретаторов. Проект декларировал Python ≥ 3.11.
- На стенде нет `python3.10-venv` (ensurepip), а `uv` не установлен.
- Mininet и OVS требуют root; Floodlight – Java-процесс.
- Нужна одна команда, которая проверяет и структуру топологий, и их работу
  в реальной сети с реальным контроллером.

## Решение

- `requires-python = ">=3.10,<4.0"`; зависимости тестов – группа `test` в
  `pyproject.toml` (`pytest>=8`, `pytest-timeout>=2.3`), `uv.lock` обновлён.
- `make venv`: `/usr/bin/python3 -m venv --without-pip --system-site-packages
.venv` и установка через системный pip.
- `make test`: `sudo env PATH=... FLOODLIGHT_JAR=... OPENFLOW=...
.venv/bin/python -m pytest -p no:cacheprovider`. Кеш pytest отключён,
  чтобы root не создавал `.pytest_cache`.
- Три этапа в одном прогоне: unit на фикстурах (без root), Mininet без
  Floodlight, Mininet + Floodlight. Если unit упали, integration
  пропускаются. `timeout = 300` на тест: `Mininet.iperf` бесконечно ждёт
  сервер при нарушенной связности.

## Последствия

- Чистый клон проверяется одной командой `make test`.
- `make test-unit` запускается без root и подходит для CI без Mininet.
- Тесты выполняются только на стенде с установленными Mininet, OVS, Java и
  собранным Floodlight.
