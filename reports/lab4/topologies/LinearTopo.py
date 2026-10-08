#!/usr/bin/env python3
"""Линейная топология из методички: k коммутаторов в цепочке, по хосту на каждом."""

from __future__ import annotations

from mininet.log import setLogLevel
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

from common import ControllerAddr, announce_hosts, make_net


class LinearTopo(Topo):
    """Linear topology of k switches, with one host per switch."""

    def build(self, k: int = 2) -> None:
        """k: number of switches (and hosts)."""
        self.k = k

        last_switch: str | None = None
        for i in range(1, k + 1):
            host = self.addHost(f"h{i}")
            switch = self.addSwitch(f"s{i}")
            self.addLink(host, switch)
            if last_switch:
                self.addLink(switch, last_switch)
            last_switch = switch


def simple_test(k: int = 4, controller: ControllerAddr | None = None) -> float:
    """Create and test a simple network, return pingAll loss in percent."""
    net = make_net(LinearTopo(k=k), controller)
    net.start()
    try:
        if controller is not None:
            net.waitConnected()
            announce_hosts(net)
        print("Dumping host connections")
        dumpNodeConnections(net.hosts)
        print("Testing network connectivity")
        return net.pingAll()
    finally:
        net.stop()


if __name__ == "__main__":
    # Tell mininet to print useful information
    setLogLevel("info")
    simple_test()
