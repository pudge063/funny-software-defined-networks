#!/usr/bin/env python3
"""Задание 1: древовидная топология ЦОД (core / aggregation / edge / host).

Каждый уровень состоит из одного слоя узлов, у каждого узла k потомков:
1 core-коммутатор -> k aggregation -> k^2 edge -> k^3 хостов.
"""

import argparse

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import irange, dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI


class CustomTopo(Topo):
    "Simple data center topology: core, aggregation, edge and host levels with fanout k."

    def __init__(self, linkopts1=None, linkopts2=None, linkopts3=None, fanout=2, **opts):
        """Init.
        linkopts1: core <-> aggregation link options
        linkopts2: aggregation <-> edge link options
        linkopts3: edge <-> host link options
        fanout: number of children of each core/aggregation/edge switch"""

        super(CustomTopo, self).__init__(**opts)

        linkopts1 = linkopts1 or {}
        linkopts2 = linkopts2 or {}
        linkopts3 = linkopts3 or {}
        self.fanout = fanout

        # switch names must contain a unique number: it becomes the datapath id
        core = self.addSwitch('cs1', dpid='%x' % 0x100)

        a = e = h = 0
        for _ in irange(1, fanout):
            a += 1
            agg = self.addSwitch('as%s' % a, dpid='%x' % (0x200 + a))
            self.addLink(agg, core, **linkopts1)
            for _ in irange(1, fanout):
                e += 1
                edge = self.addSwitch('es%s' % e, dpid='%x' % (0x300 + e))
                self.addLink(edge, agg, **linkopts2)
                for _ in irange(1, fanout):
                    h += 1
                    host = self.addHost('h%s' % h)
                    self.addLink(host, edge, **linkopts3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-k', '--fanout', type=int, default=2)
    parser.add_argument('--cli', action='store_true', help='open Mininet CLI after tests')
    args = parser.parse_args()

    # пропускная способность уменьшается от ядра к хостам
    linkopts1 = dict(bw=100, delay='1ms')
    linkopts2 = dict(bw=50, delay='2ms')
    linkopts3 = dict(bw=10, delay='5ms')

    topo = CustomTopo(linkopts1, linkopts2, linkopts3, fanout=args.fanout)
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    print("Dumping host connections")
    dumpNodeConnections(net.hosts)
    print("Testing network connectivity")
    net.pingAll()

    first, last = net.hosts[0], net.hosts[-1]
    print("Testing latency between %s and %s (via core)" % (first.name, last.name))
    print(first.cmd('ping -c 4 %s' % last.IP()))
    print("Testing bandwidth between %s and %s" % (first.name, last.name))
    net.iperf((first, last))
    if args.cli:
        CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
