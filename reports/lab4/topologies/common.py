"""Общие типы и хелперы для топологий лабораторной 4."""

from __future__ import annotations

import argparse
import ipaddress
from functools import partial
from typing import Any, NamedTuple, TypedDict

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo
from mininet.util import quietRun


class LinkOpts(TypedDict, total=False):
    """Параметры TCLink, типы совпадают с тем, что ожидает Mininet."""

    bw: float  # Мбит/с
    delay: str  # '5ms', '1us', ...
    jitter: str
    loss: float  # проценты, 0..100
    max_queue_size: int  # пакеты
    use_htb: bool


class ControllerAddr(NamedTuple):
    ip: str
    port: int

    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"


DEFAULT_CONTROLLER = ControllerAddr("127.0.0.1", 6653)

OPENFLOW_VERSIONS = ("OpenFlow10", "OpenFlow13")
DEFAULT_OPENFLOW = "OpenFlow13"


def parse_controller(value: str) -> ControllerAddr:
    """argparse type: 'ip:port' -> ControllerAddr."""
    ip, sep, port = value.rpartition(":")
    if not sep or not ip or not port.isdigit() or not 0 < int(port) < 65536:
        raise argparse.ArgumentTypeError(f"expected ip:port, got {value!r}")
    return ControllerAddr(ip, int(port))


def positive_int(value: str) -> int:
    """argparse type: целое > 0."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"expected integer >= 1, got {value!r}")
    return number


def disable_ipv6(net: Mininet) -> None:
    """Отключить IPv6 на хостах и портах коммутаторов.

    Ядро помечает MLD-отчёты (skb mark), OVS 2.17 передаёт метку в OF1.3
    packet-in как NXM-поле pkt_mark, а Floodlight 1.2 его не знает: падает на
    разборе сообщения и разрывает соединение с коммутатором.
    """
    for host in net.hosts:
        host.cmd(
            "sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1"
        )
    for switch in net.switches:
        for intf in switch.intfNames():
            if intf != "lo":
                quietRun(f"sysctl -qw net.ipv6.conf.{intf}.disable_ipv6=1")


def announce_hosts(net: Mininet) -> None:
    """Каждый хост отправляет широковещательный ping.

    Floodlight не флудит ARP для известных ему IP, а отправляет запрос туда, где
    видел устройство в последний раз. Если до этого на том же контроллере
    работала другая сеть с теми же адресами, ARP уходит в устаревший порт.
    Пакет от хоста обновляет его точку подключения в Floodlight. Хосты без
    IPv6 сами ничего не шлют, поэтому их нужно «объявить».
    """
    for host in net.hosts:
        intf = host.defaultIntf()
        network = ipaddress.ip_interface(f"{intf.IP()}/{intf.prefixLen}").network
        host.cmd(f"ping -c 1 -W 1 -b {network.broadcast_address}")


def make_net(
    topo: Topo,
    controller: ControllerAddr | None = None,
    protocols: str = DEFAULT_OPENFLOW,
    **kwargs: Any,
) -> Mininet:
    """Собрать сеть Mininet.

    controller=None: контроллер Mininet по умолчанию (c0);
    иначе OVS с версией OpenFlow protocols подключается к внешнему контроллеру,
    например Floodlight. IPv6 в этом случае отключается, см. disable_ipv6.
    """
    if controller is None:
        return Mininet(topo=topo, **kwargs)
    kwargs.setdefault("switch", partial(OVSSwitch, protocols=protocols))
    net = Mininet(topo=topo, controller=None, **kwargs)
    net.addController(
        "c0", controller=RemoteController, ip=controller.ip, port=controller.port
    )
    disable_ipv6(net)
    return net
