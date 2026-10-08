#!/usr/bin/env python3
"""Линейная топология с CPULimitedHost и TCLink (bw, delay, loss, очередь)."""

from __future__ import annotations

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.node import CPULimitedHost
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

from common import ControllerAddr, LinkOpts, announce_hosts, make_net

# 10 Mbps, 5ms delay, 1% loss, 1000 packet queue
DEFAULT_LINKOPTS: LinkOpts = {
    "bw": 10.0,
    "delay": "5ms",
    "loss": 1.0,
    "max_queue_size": 1000,
    "use_htb": True,
}


class LinearTopo(Topo):
    """Linear topology of k switches, with one host per switch."""

    def build(self, k: int = 2, linkopts: LinkOpts | None = None) -> None:
        """k: number of switches (and hosts)
        linkopts: options for every link, DEFAULT_LINKOPTS if omitted"""
        self.k = k
        if linkopts is None:
            linkopts = DEFAULT_LINKOPTS

        last_switch: str | None = None
        for i in range(1, k + 1):
            host = self.addHost(f"h{i}", cpu=0.5 / k)
            switch = self.addSwitch(f"s{i}")
            self.addLink(host, switch, **linkopts)
            if last_switch:
                self.addLink(switch, last_switch, **linkopts)
            last_switch = switch


def perf_test(
    k: int = 4,
    linkopts: LinkOpts | None = None,
    controller: ControllerAddr | None = None,
) -> tuple[float, list[str]]:
    """Create network and run simple performance test.

    Returns pingAll loss in percent and iperf result (server, client)."""
    topo = LinearTopo(k=k, linkopts=linkopts)
    net = make_net(topo, controller, host=CPULimitedHost, link=TCLink)
    net.start()
    try:
        if controller is not None:
            net.waitConnected()
            announce_hosts(net)
        print("Dumping host connections")
        dumpNodeConnections(net.hosts)
        print("Testing network connectivity")
        loss = net.pingAll()
        first, last = net.hosts[0], net.hosts[-1]
        print(f"Testing bandwidth between {first.name} and {last.name}")
        return loss, net.iperf((first, last))
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    perf_test()
