# lab1-sdn-testbed Specification

## Purpose

Лабораторная работа 1 «Запуск модельной сети SDN»: подготовка ВМ, установка
Mininet, сборка и запуск контроллера Floodlight v1.2, подключение к нему
эмулируемой сети. Результат лабы – стенд, на котором выполняются lab 2–4.

Артефакты:

- отчёт: `reports/lab1/report.md` (только скриншоты `images/image1.png` …
  `image13.png`, текстовых выводов нет);
- процедура установки: `README.md`, раздел Installation Docs;
- сводка: `SUMMARY.md`, раздел Lab 1.

Общие требования к стенду – `specs/sdn-lab-environment`.

## Requirements

### Requirement: Установка Mininet

Mininet SHALL устанавливаться из исходников `https://github.com/mininet/mininet`
в `~/mininet` скриптом `util/install.sh -a`. Установка MUST делать Mininet
доступным из `/usr/bin/python3` и команду `mn` – из `PATH`.

#### Scenario: Простейшая сеть

- **WHEN** выполняется `sudo mn`
- **THEN** создаются h1, h2, s1 и контроллер c0
- **AND** `mininet> pingall` сообщает `0% dropped (2/2 received)`

#### Scenario: Линейная сеть без внешнего контроллера

- **WHEN** выполняется `sudo mn --topo linear,4 --switch ovsk`
- **THEN** `mininet> pingall` сообщает `0% dropped (12/12 received)`
- **AND** `mininet> h1 ping h3` проходит без потерь

### Requirement: Сборка Floodlight на Ubuntu 22.04

Floodlight v1.2 SHALL собираться командой `ant dist` в `~/floodlight` под
Java 8 после выполнения всех шагов процедуры R1 (раздел Reference) в
указанном порядке.

#### Scenario: Успешная сборка

- **WHEN** шаги 1–6 выполнены и запущен `ant dist`
- **THEN** создаётся `~/floodlight/target/floodlight.jar`

### Requirement: Подключение сети к Floodlight

Линейная сеть из 4 коммутаторов SHALL подключаться к Floodlight через
`--controller=remote,ip=<IP контроллера>,port=6653`. Каждый коммутатор MUST
пройти OpenFlow handshake и получить роль MASTER.

#### Scenario: Сеть под управлением Floodlight

- **WHEN** Floodlight запущен из `~/floodlight` и выполнено
  `sudo mn --topo linear,4 --switch ovsk --controller=remote,ip=127.0.0.1,port=6653`
- **THEN** лог Floodlight содержит по одной строке `Switch OFSwitch DPID[...]
bound to class` и `Defining switch role from config file: ROLE_MASTER` на
  каждый из 4 коммутаторов
- **AND** `mininet> pingall` сообщает `0% dropped (12/12 received)`

### Requirement: Отображение топологии в web UI

Web-интерфейс Floodlight SHALL быть доступен на `http://<IP>:8080/ui/` и на
странице Topology MUST отображать все коммутаторы и хосты подключённой сети.

#### Scenario: Топология linear,4 в UI

- **WHEN** сеть linear,4 подключена к Floodlight и выполнен `pingall`
- **THEN** на странице Topology отображаются 4 коммутатора и 4 хоста

## Reference

### R1. Процедура сборки Floodlight

Исходный проект несовместим с инструментами Ubuntu 22.04, поэтому перед
`ant dist` выполняются шаги:

1. сборка и установка Thrift 0.9.3 из исходников (`./configure` без
   биндингов Python/Java/C++/Qt, `make`, `sudo make install`);
2. замена `lib/libthrift-0.9.0.jar` на `libthrift-0.9.3.jar` из Maven Central;
3. удаление и повторная генерация Java-кода Thrift для
   `src/main/thrift/packetstreamer.thrift` и `src/main/thrift/sync.thrift`;
4. замена импорта `org.apache.thrift.transport.layered.TFramedTransport` на
   `org.apache.thrift.transport.TFramedTransport` в `PacketStreamerClient.java`
   и `PacketStreamerServer.java`;
5. удаление аннотации `@Override` (строка 105) в
   `src/test/java/net/floodlightcontroller/core/test/TestEventLoop.java`;
6. переключение `java` на версию 8.

Точные команды – `README.md`, раздел «floodlight installation». Известные
опечатки в README – `specs/sdn-lab-environment`, требование «Известные
дефекты документации установки».
