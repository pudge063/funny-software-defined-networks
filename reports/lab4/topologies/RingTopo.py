#!/usr/bin/env python3
"""Задание 2: кольцевая топология.

n коммутаторов соединены в кольцо (s1-s2-...-sn-s1), к каждому коммутатору
подключено k хостов (fanout). Для каждого соединения задаются bw и delay:
отдельно для звеньев кольца (switch-switch) и для звеньев доступа (host-switch).

В кольце есть петля, поэтому сеть запускается с внешним контроллером
Floodlight (строит дерево для широковещательного трафика) либо, с ключом
--stp, с OVS в режиме standalone и включённым STP.
"""

import argparse
import time

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost, OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.util import irange, dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI


class RingTopo(Topo):
    "Ring of n switches, k hosts per switch."

    def __init__(self, n=3, k=3, ringopts=None, hostopts=None, **opts):
        """Init.
        n: number of switches in the ring
        k: fanout - number of hosts per switch
        ringopts: switch <-> switch link options (bw, delay, ...)
        hostopts: host <-> switch link options (bw, delay, ...)"""

        super(RingTopo, self).__init__(**opts)

        ringopts = ringopts or {}
        hostopts = hostopts or {}

        switches = [self.addSwitch('s%s' % i) for i in irange(1, n)]

        h = 0
        for switch in switches:
            for _ in irange(1, k):
                h += 1
                host = self.addHost('h%s' % h)
                self.addLink(host, switch, **hostopts)

        for i in range(n):
            # s1-s2, s2-s3, ..., sn-s1: last link closes the ring
            if n > 2 or i < n - 1:
                self.addLink(switches[i], switches[(i + 1) % n], **ringopts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-n', '--switches', type=int, default=3)
    parser.add_argument('-k', '--fanout', type=int, default=3)
    parser.add_argument('--ring-bw', type=float, default=20, help='Mbit/s')
    parser.add_argument('--ring-delay', default='10ms')
    parser.add_argument('--host-bw', type=float, default=10, help='Mbit/s')
    parser.add_argument('--host-delay', default='1ms')
    parser.add_argument('--controller', default='127.0.0.1:6653', help='remote controller ip:port')
    parser.add_argument('--stp', action='store_true', help='no controller, OVS standalone + STP')
    parser.add_argument('--cli', action='store_true', help='open Mininet CLI after tests')
    args = parser.parse_args()

    topo = RingTopo(
        n=args.switches,
        k=args.fanout,
        ringopts=dict(bw=args.ring_bw, delay=args.ring_delay),
        hostopts=dict(bw=args.host_bw, delay=args.host_delay),
    )

    if args.stp:
        net = Mininet(
            topo=topo, host=CPULimitedHost, link=TCLink, controller=None,
            switch=lambda name, **kw: OVSSwitch(name, failMode='standalone', stp=True, **kw),
        )
    else:
        ip, port = args.controller.split(':')
        net = Mininet(
            topo=topo, host=CPULimitedHost, link=TCLink, controller=None,
            switch=lambda name, **kw: OVSSwitch(name, protocols='OpenFlow13', **kw),
        )
        net.addController('c0', controller=RemoteController, ip=ip, port=int(port))

    net.start()
    net.waitConnected()
    if args.stp:
        print("Waiting for STP convergence")
        time.sleep(35)
    else:
        print("Waiting for controller link discovery (LLDP)")
        time.sleep(20)
    print("Dumping host connections")
    dumpNodeConnections(net.hosts)
    print("Dumping switch connections")
    dumpNodeConnections(net.switches)
    print("Testing network connectivity")
    net.pingAll()

    h1 = net.hosts[0]
    near = net.hosts[1]                   # same switch as h1
    far = net.hosts[args.fanout]          # first host on the next switch
    for dst in (near, far):
        print("Testing latency between %s and %s" % (h1.name, dst.name))
        print(h1.cmd('ping -c 4 %s' % dst.IP()))
    print("Testing bandwidth between %s and %s" % (h1.name, far.name))
    net.iperf((h1, far))
    if args.cli:
        CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
