# funny-software-defined-networks

## Labs reports

[Summary по всем лабам](./SUMMARY.md)

- [Lab 1](./reports/lab1/report.md)
- [Lab 2](./reports/lab2/report.md)
- [Lab 3](./reports/lab3/report.md)
- [Lab 4](./reports/lab4/report.md)

Тесты для топологий lab 4 описаны в разделе [Tests](#tests).

## Tests

Топологии из [lab 4](./reports/lab4/topologies) проверяются через `pytest`. Все
тесты запускаются одной командой из корня репозитория:

```
make test
```

Что делает `make test`:

1. создаёт `.venv` на системном `/usr/bin/python3` с `--system-site-packages`
   (Mininet ставится `install.sh` именно туда) и ставит `pytest` и
   `pytest-timeout`;
1. запускает `pytest` через `sudo`, потому что Mininet нужен root;
1. гоняет тесты по этапам:
   - **unit-тесты на фикстурах** (`tests/test_topologies.py`, root не нужен):
     фикстура `topo_case` параметризована всеми топологиями (linear, linear perf,
     tree с k = 1..3, ring с разными n и k) и проверяет число узлов и связей,
     связность графа, уникальность DPID, типы параметров `TCLink` (`bw` – число,
     `delay` – строка вида `5ms`, `max_queue_size` – int и т. д.), форму дерева и
     кольца, разбор аргументов CLI;
   - **Mininet без контроллера Floodlight**: `LinearTopo.py` с контроллером
     Mininet по умолчанию и кольцо в режиме OVS standalone + STP (тест ждёт
     сходимости STP и проверяет, что в кольце есть заблокированный порт);
   - **Mininet + Floodlight** (`tests/test_integration.py`): session-фикстура
     `floodlight` запускает `java -jar floodlight.jar` и гасит его в конце.
     Фикстура `floodlight_net` поднимает по одной сети на топологию (linear,
     linear perf, tree k = 2, ring 2 x 2 и 3 x 3) по OpenFlow 1.3 и ждёт, пока
     контроллер увидит все коммутаторы и найдёт через LLDP ровно те связи, что
     есть в топологии. Затем тесты сверяют топологию через REST API, проверяют
     `pingAll` без потерь и `iperf` в пределах самого узкого звена.

Перед каждой топологией Floodlight перезапускается. Floodlight 1.2 помнит
связи и устройства прошлой сети, и когда коммутаторы с теми же DPID быстро
переподключаются, он строит маршруты по устаревшим данным: часть хостов
становится недоступна. Если Floodlight уже запущен (REST API отвечает на
`:8080`), тесты используют его и не перезапускают. Тогда такие сбои возможны, а
тест с контроллером Mininet по умолчанию пропускается, потому что порт 6653
занят. Для чистого прогона остановите свой Floodlight перед `make test`.

Если упал хоть один unit-тест, integration-тесты пропускаются. Каждый тест
ограничен 300 с (`pytest-timeout`), поэтому сломанная связность не подвешивает
`iperf`.

Другие цели и параметры:

```
make test-unit                      # только тесты на фикстурах, без sudo
make test-integration               # только Mininet + Floodlight
make test PYTEST_ARGS="-v -k ring"  # аргументы для pytest
make test FLOODLIGHT_JAR=/path/to/floodlight.jar
make test OPENFLOW=OpenFlow10       # версия OpenFlow для коммутаторов под Floodlight
make clean                          # sudo mn -c и удалить .venv
```

По умолчанию берётся `~/floodlight/target/floodlight.jar` (сборка описана ниже).
Полный прогон занимает около 3 минут.

Floodlight 1.2 на OpenFlow 1.0 падает в модуле `Forwarding`
(`OFMatch does not support matching on field ovs_tcp_flags`) и не ставит
правила для TCP, поэтому `iperf` на `OPENFLOW=OpenFlow10` не работает.

## Installation Docs

### initial configuration

update packages: `sudo apt-get update -y && sudo apt-get upgrade -y`

### mininet installation

reference: https://mininet.org/download/

clone mininet repo: `git clone https://github.com/mininet/mininet ~/mininet`

show actual tags: `git -C ~/mininet tag`

checkout tag: `git -C ~/mininet checkout -b 2.3.0`

install mininet: `mininet/util/install.sh -a`

### floodlight installation

build and install thrift 0.9.3

```
sudo apt install -y \
    libboost-dev \
    libboost-test-dev \
    libboost-program-options-dev \
    libevent-dev \
    automake \
    libtool \
    flex \
    bison \
    pkg-config \
    g++ \
    libssl-dev \
    make

wget http://archive.apache.org/dist/thrift/0.9.3/thrift-0.9.3.tar.gz
tar -xzf thrift-0.9.3.tar.gz
cd thrift-0.9.3

./configure --without-python --without-java-package --without-c_glib \
    --without-tests --without-cpp --without-qt4 --without-qt5

make -j$(nproc)

sudo make install

hash -r

thrift --version
```

install required packages:

reference: https://floodlight.atlassian.net/wiki/spaces/floodlightcontroller/pages/1343544/Installation+Guide#Installation

```
# ubuntu < 22.04
sudo apt-get install build-essential openjdk-7-jdk ant maven python-dev eclipse

# actual, ubuntu 22.04

sudo apt-get install build-essential openjdk-8-jdk ant git
```

clone floodlight repo: `git clone https://github.com/floodlight/floodlight.git ~/floodlight`

show actual tags: `git -C ~/floodlight tag`

checkout tag: `git -C ~/floodlight checkout -b v1.2`

init submodules: `git -C ~/floodlight submodules update --init`

chdir to floodlight: `cd ~/floodlight`

replace libthrift binary: `wget https://repo1.maven.org/maven2/org/apache/thrift/libthrift/0.9.3/libthrift-0.9.3.jar -O lib/libthrift-0.9.0.jar`

generate new thrift files:

```
find . -name "*.thrift"

rm -rf lib/gen-java/net/floodlightcontroller/packetstreamer/thrift
rm -rf lib/gen-java/org/sdnplatform/sync/thrift

thrift --gen java -out lib/gen-java src/main/thrift/packetstreamer.thrift
thrift --gen java -out lib/gen-java src/main/thrift/sync.thrift
```

apply new path for Java classes:

```
sed -i 's/org\.apache\.thrift\.transport\.layered\.TFramedTransport/org.apache.thrift.transport.TFramedTransport/' \
    src/main/java/net/floodlightcontroller/packetstreamer/PacketStreamerClient.java \
    src/main/java/net/floodlightcontroller/packetstreamer/PacketStreamerServer.java
```

remove `@Override` notation from class:

`sed -i '105d' src/test/java/net/floodlightcontroller/core/test/TestEventLoop.java`

set java to 8 version: `java -version`

build floodlight binary: `ant dist`

built binary in `~/floodlight/target/floodlight.jar`

run floodlight service: `java -jar target/floodlight.jar`

### Install wireshark

reference: https://launchpad.net/~wireshark-dev/+archive/ubuntu/stable

```
sudo add-apt-repository ppa:wireshark-dev/stable
sudo apt update

sudo apt-get install wireshark
```
