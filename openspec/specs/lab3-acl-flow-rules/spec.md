# lab3-acl-flow-rules Specification

## Purpose

Лабораторная работа 3 «Создание правил обработки потока на контроллере SDN»:
создание правила ACL в Floodlight, проверка его влияния на связность хостов,
на таблицу потоков коммутатора и на обмен OpenFlow.

Артефакты:

- отчёт: `reports/lab3/report.md` (команды, `dump-flows` до и после правила,
  разбор `OFPT_FLOW_MOD`, таблица OpenFlow-сообщений потока h1 ↔ h4, ответы на
  контрольные вопросы), скриншоты `images/image1.png` … `image8.png`;
- сводка: `SUMMARY.md`, раздел Lab 3.

Файл захвата (`/tmp/lab3_capture.pcap`) в репозиторий не входит. Общие
требования к стенду – `specs/sdn-lab-environment`, разбор протокола –
`specs/lab2-openflow-capture`.

## Requirements

### Requirement: Исходная конфигурация

Эксперимент SHALL выполняться в следующем порядке: захват
`sudo tshark -i any -f "tcp port 6653" -w /tmp/lab3_capture.pcap`, запуск
Floodlight, сеть
`sudo mn --topo linear,4 --switch ovsk,protocols=OpenFlow13 --ipbase=10.0.0.0/8 --controller=remote,ip=127.0.0.1,port=6653`,
затем `mininet> pingall` до создания правила.

#### Scenario: Связность до правила

- **WHEN** выполнен `pingall` до создания правила ACL
- **THEN** результат – `0% dropped (12/12 received)`
- **AND** таблица потоков s1 содержит только table-miss
  `priority=0 actions=CONTROLLER:65535` (и, пока не истекли, правила
  Forwarding с `priority=1`)

### Requirement: Правило ACL

Правило SHALL блокировать ICMP от h1 к h4 и задаваться одним из
эквивалентных способов:

- web UI: Access Control Lists → Add New, протокол ICMP, источник
  `10.0.0.1/32`, назначение `10.0.0.4/32`, действие DENY;
- REST:
  `curl -X POST -d '{"src-ip":"10.0.0.1/32","dst-ip":"10.0.0.4/32","nw-proto":"ICMP","action":"DENY"}' http://127.0.0.1:8080/wm/acl/rules/json`.

#### Scenario: Установка правила в коммутатор

- **WHEN** правило создано
- **THEN** контроллер проактивно, без предшествующего `OFPT_PACKET_IN`,
  отправляет на s1 (пограничный коммутатор h1) ровно одно `OFPT_FLOW_MOD`:
  `command=OFPFC_ADD`, `priority=30000`, `idle_timeout=0`, `hard_timeout=0`,
  `flags=OFPFF_SEND_FLOW_REM`, match `eth_type=0x0800, ip_proto=1,
ipv4_src=10.0.0.1, ipv4_dst=10.0.0.4`, без инструкций
- **AND** `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` показывает запись
  `send_flow_rem priority=30000,icmp,nw_src=10.0.0.1,nw_dst=10.0.0.4 actions=drop`
- **AND** на s2–s4 правило ACL не устанавливается

### Requirement: Влияние правила на связность

После создания правила ICMP-связность SHALL пропадать только между h1 и h4,
в обоих направлениях; все остальные пары MUST оставаться доступными;
не-ICMP трафик между h1 и h4 MUST NOT блокироваться.

#### Scenario: pingall после правила

- **WHEN** выполнен `pingall` после создания правила
- **THEN** результат – `16% dropped (10/12 received)`
- **AND** строки `h1 -> h2 h3 X` и `h4 -> X h2 h3`

#### Scenario: Причина недоступности h4 → h1

- **WHEN** h4 пингует h1
- **THEN** эхо-запрос 10.0.0.4 → 10.0.0.1 доходит до h1
- **AND** эхо-ответ 10.0.0.1 → 10.0.0.4 совпадает с правилом и
  отбрасывается на s1

#### Scenario: Счётчик правила

- **WHEN** после правила выполнены `pingall` и `h1 ping -c 3 h4`
- **THEN** у записи priority 30000 на s1 `n_packets=5` (2 от `pingall`,
  3 от `ping -c 3`)

### Requirement: Влияние правила на обмен OpenFlow

Для заблокированного направления 10.0.0.1 → 10.0.0.4 обмен с контроллером
SHALL прекращаться полностью; для остальных потоков MUST оставаться
реактивным. Ожидаемое число сообщений – таблица R1 (раздел Reference).

#### Scenario: Фильтр для анализа

- **WHEN** анализируется захват
- **THEN** используется фильтр
  `(openflow_v4.type == 10 || openflow_v4.type == 14) && ((icmp && ip.src == 10.0.0.1 && ip.dst == 10.0.0.4) || (openflow_v4.oxm.value_ipv4addr == 10.0.0.1 && openflow_v4.oxm.value_ipv4addr == 10.0.0.4))`
- **AND** коммутатор определяется по TCP-порту со стороны коммутатора,
  сопоставленному по `FEATURES_REPLY`

#### Scenario: FLOW_MOD правила ACL

- **WHEN** выполняется
  `tshark -r /tmp/lab3_capture.pcap -O openflow_v4 -Y 'openflow_v4.type == 14 && openflow_v4.flowmod.priority == 30000'`
- **THEN** выводится ровно одно сообщение, адресованное s1

### Requirement: Приоритеты правил

Интерпретация таблицы потоков SHALL опираться на следующие приоритеты
Floodlight 1.2: ACL – 30000, Forwarding – 1, table-miss – 0. Правило ACL
MUST иметь приоритет выше правил Forwarding, иначе блокировка не
гарантируется.

#### Scenario: Конфликт с правилом Forwarding

- **WHEN** на s1 одновременно есть правило Forwarding priority 1 для
  h1 → h4 и правило ACL priority 30000
- **THEN** пакеты ICMP h1 → h4 совпадают с правилом ACL и отбрасываются

## Reference

### R1. OpenFlow-сообщения потока h1 ↔ h4

| Поток / этап                    | PACKET_IN                                   | PACKET_OUT | FLOW_MOD               |
| ------------------------------- | ------------------------------------------- | ---------- | ---------------------- |
| 10.0.0.1 → 10.0.0.4, до правила | 1                                           | 1          | 4 (по одному на s1–s4) |
| создание правила                | 0                                           | 0          | 1 (s1, priority 30000) |
| 10.0.0.1 → 10.0.0.4, после      | 0                                           | 0          | 0                      |
| 10.0.0.4 → 10.0.0.1, после      | без изменений: FLOW_MOD priority 1 на s1–s4 |
