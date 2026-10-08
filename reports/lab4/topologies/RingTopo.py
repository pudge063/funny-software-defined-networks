#!/usr/bin/env python3
"""Задание 2: кольцевая топология.

n коммутаторов соединены в кольцо (s1-s2-...-sn-s1), к каждому коммутатору
подключено k хостов (fanout). Для каждого соединения задаются bw и delay:
отдельно для звеньев кольца (switch-switch) и для звеньев доступа (host-switch).

В кольце есть петля, поэтому сеть запускается с внешним контроллером
Floodlight (строит дерево для широковещательного трафика) либо, с ключом
--stp, с OVS в режиме standalone и включённым STP.
"""

from __future__ import annotations

import argparse
import time
from functools import partial

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import CPULimitedHost, OVSSwitch
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

from common import (
    DEFAULT_CONTROLLER,
    DEFAULT_OPENFLOW,
    OPENFLOW_VERSIONS,
    ControllerAddr,
    LinkOpts,
    announce_hosts,
    make_net,
    parse_controller,
    positive_int,
)

# состояния порта STP в OVS, после которых он больше не меняется
STP_STABLE_STATES = frozenset({"forwarding", "blocking", "disabled"})


class RingTopo(Topo):
    """Ring of n switches, k hosts per switch."""

    def build(
        self,
        n: int = 3,
        k: int = 3,
        ringopts: LinkOpts | None = None,
        hostopts: LinkOpts | None = None,
    ) -> None:
        """n: number of switches in the ring
        k: fanout - number of hosts per switch
        ringopts: switch <-> switch link options (bw, delay, ...)
        hostopts: host <-> switch link options (bw, delay, ...)"""
        ringopts = ringopts or {}
        hostopts = hostopts or {}

        switches = [self.addSwitch(f"s{i}") for i in range(1, n + 1)]

        h = 0
        for switch in switches:
            for _ in range(k):
                h += 1
                host = self.addHost(f"h{h}")
                self.addLink(host, switch, **hostopts)

        for i in range(n):
            # s1-s2, s2-s3, ..., sn-s1: last link closes the ring
            if n > 2 or i < n - 1:
                self.addLink(switches[i], switches[(i + 1) % n], **ringopts)


def make_ring_net(
    topo: RingTopo,
    controller: ControllerAddr | None,
    protocols: str = DEFAULT_OPENFLOW,
) -> Mininet:
    """controller=None: без контроллера, OVS standalone + STP."""
    if controller is None:
        return Mininet(
            topo=topo,
            host=CPULimitedHost,
            link=TCLink,
            controller=None,
            switch=partial(OVSSwitch, failMode="standalone", stp=True),
        )
    return make_net(topo, controller, protocols, host=CPULimitedHost, link=TCLink)


def stp_converged(net: Mininet) -> bool:
    for switch in net.switches:
        for intf in switch.intfList():
            if intf.name == "lo":
                continue
            state = switch.vsctl("get", "Port", intf.name, "status:stp_state")
            if state.strip().strip('"') not in STP_STABLE_STATES:
                return False
    return True


def wait_stp(net: Mininet, timeout: float = 60.0) -> bool:
    """Дождаться, пока все порты STP выйдут из listening/learning."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stp_converged(net):
            return True
        time.sleep(1)
    return False


def run(
    topo: RingTopo,
    controller: ControllerAddr | None,
    protocols: str = DEFAULT_OPENFLOW,
    discovery_time: float = 20.0,
    cli: bool = False,
) -> None:
    net = make_ring_net(topo, controller, protocols)
    net.start()
    try:
        net.waitConnected()
        if controller is None:
            info("*** Waiting for STP convergence\n")
            if not wait_stp(net):
                info("*** STP has not converged, continuing anyway\n")
        else:
            info("*** Waiting for controller link discovery (LLDP)\n")
            time.sleep(discovery_time)
            announce_hosts(net)
        print("Dumping host connections")
        dumpNodeConnections(net.hosts)
        print("Dumping switch connections")
        dumpNodeConnections(net.switches)
        print("Testing network connectivity")
        net.pingAll()

        h1 = net.hosts[0]
        fanout = len(net.hosts) // len(net.switches)
        # хост на том же коммутаторе и первый хост на следующем
        peers = [net.hosts[i] for i in (1, fanout) if 0 < i < len(net.hosts)]
        for dst in dict.fromkeys(peers):
            print(f"Testing latency between {h1.name} and {dst.name}")
            print(h1.cmd(f"ping -c 4 {dst.IP()}"))
        if peers:
            far = peers[-1]
            print(f"Testing bandwidth between {h1.name} and {far.name}")
            net.iperf((h1, far))
        if cli:
            CLI(net)
    finally:
        net.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--switches", type=positive_int, default=3)
    parser.add_argument("-k", "--fanout", type=positive_int, default=3)
    parser.add_argument("--ring-bw", type=float, default=20.0, help="Mbit/s")
    parser.add_argument("--ring-delay", default="10ms")
    parser.add_argument("--host-bw", type=float, default=10.0, help="Mbit/s")
    parser.add_argument("--host-delay", default="1ms")
    parser.add_argument(
        "--controller",
        type=parse_controller,
        default=DEFAULT_CONTROLLER,
        help=f"remote controller ip:port (default: {DEFAULT_CONTROLLER})",
    )
    parser.add_argument(
        "--discovery-time",
        type=float,
        default=20.0,
        help="seconds to wait for controller LLDP discovery",
    )
    parser.add_argument(
        "--stp", action="store_true", help="no controller, OVS standalone + STP"
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

    topo = RingTopo(
        n=args.switches,
        k=args.fanout,
        ringopts={"bw": args.ring_bw, "delay": args.ring_delay},
        hostopts={"bw": args.host_bw, "delay": args.host_delay},
    )
    controller = None if args.stp else args.controller
    run(topo, controller, args.protocols, args.discovery_time, args.cli)


if __name__ == "__main__":
    setLogLevel("info")
    main()
