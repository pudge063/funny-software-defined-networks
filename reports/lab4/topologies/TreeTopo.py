#!/usr/bin/env python3
"""Задание 1: древовидная топология ЦОД (core / aggregation / edge / host).

Каждый уровень состоит из одного слоя узлов, у каждого узла k потомков:
1 core-коммутатор -> k aggregation -> k^2 edge -> k^3 хостов.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import CPULimitedHost
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

from common import (
    DEFAULT_OPENFLOW,
    OPENFLOW_VERSIONS,
    ControllerAddr,
    LinkOpts,
    announce_hosts,
    make_net,
    parse_controller,
    positive_int,
)

# пропускная способность уменьшается от ядра к хостам
CORE_LINKOPTS: LinkOpts = {"bw": 100.0, "delay": "1ms"}
AGGREGATION_LINKOPTS: LinkOpts = {"bw": 50.0, "delay": "2ms"}
EDGE_LINKOPTS: LinkOpts = {"bw": 10.0, "delay": "5ms"}

# DPID = префикс уровня + порядковый номер коммутатора
CORE_DPID = 0x100
AGGREGATION_DPID = 0x200
EDGE_DPID = 0x300


def dpid(prefix: int, number: int) -> str:
    """Mininet принимает DPID строкой из hex-цифр."""
    return f"{prefix + number:x}"


class CustomTopo(Topo):
    """Simple data center topology: core, aggregation, edge and host levels with fanout k."""

    def build(
        self,
        linkopts1: LinkOpts | None = None,
        linkopts2: LinkOpts | None = None,
        linkopts3: LinkOpts | None = None,
        fanout: int = 2,
    ) -> None:
        """linkopts1: core <-> aggregation link options
        linkopts2: aggregation <-> edge link options
        linkopts3: edge <-> host link options
        fanout: number of children of each core/aggregation/edge switch"""
        linkopts1 = linkopts1 or {}
        linkopts2 = linkopts2 or {}
        linkopts3 = linkopts3 or {}
        self.fanout = fanout

        # switch names must contain a unique number: it becomes the datapath id
        core = self.addSwitch("cs1", dpid=dpid(CORE_DPID, 0))

        e = h = 0
        for a in range(1, fanout + 1):
            agg = self.addSwitch(f"as{a}", dpid=dpid(AGGREGATION_DPID, a))
            self.addLink(agg, core, **linkopts1)
            for _ in range(fanout):
                e += 1
                edge = self.addSwitch(f"es{e}", dpid=dpid(EDGE_DPID, e))
                self.addLink(edge, agg, **linkopts2)
                for _ in range(fanout):
                    h += 1
                    host = self.addHost(f"h{h}")
                    self.addLink(host, edge, **linkopts3)


@dataclass(frozen=True)
class TreeResult:
    ping_loss: float  # проценты
    iperf: list[str]  # [server, client]


def run(
    fanout: int = 2,
    controller: ControllerAddr | None = None,
    protocols: str = DEFAULT_OPENFLOW,
    discovery_time: float = 20.0,
    cli: bool = False,
) -> TreeResult:
    topo = CustomTopo(CORE_LINKOPTS, AGGREGATION_LINKOPTS, EDGE_LINKOPTS, fanout=fanout)
    net = make_net(topo, controller, protocols, host=CPULimitedHost, link=TCLink)
    net.start()
    try:
        if controller is not None:
            net.waitConnected()
            info("*** Waiting for controller link discovery (LLDP)\n")
            time.sleep(discovery_time)
            announce_hosts(net)
        print("Dumping host connections")
        dumpNodeConnections(net.hosts)
        print("Testing network connectivity")
        loss = net.pingAll()

        first, last = net.hosts[0], net.hosts[-1]
        print(f"Testing latency between {first.name} and {last.name} (via core)")
        print(first.cmd(f"ping -c 4 {last.IP()}"))
        print(f"Testing bandwidth between {first.name} and {last.name}")
        iperf = net.iperf((first, last))
        if cli:
            CLI(net)
        return TreeResult(loss, iperf)
    finally:
        net.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-k", "--fanout", type=positive_int, default=2)
    parser.add_argument(
        "--controller",
        type=parse_controller,
        default=None,
        help="remote controller ip:port (default: Mininet controller c0)",
    )
    parser.add_argument(
        "--discovery-time",
        type=float,
        default=20.0,
        help="seconds to wait for controller LLDP discovery (with --controller)",
    )
    parser.add_argument(
        "--protocols",
        choices=OPENFLOW_VERSIONS,
        default=DEFAULT_OPENFLOW,
        help="OpenFlow version for the remote controller",
    )
    parser.add_argument(
        "--cli", action="store_true", help="open Mininet CLI after tests"
    )
    args = parser.parse_args()
    run(args.fanout, args.controller, args.protocols, args.discovery_time, args.cli)


if __name__ == "__main__":
    setLogLevel("info")
    main()
