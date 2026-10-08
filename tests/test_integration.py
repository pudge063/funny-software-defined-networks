"""Запуск топологий в настоящем Mininet с контроллером Floodlight (нужен root)."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import CPULimitedHost

from common import announce_hosts, make_net
from conftest import (
    TOPO_CASES,
    Floodlight,
    TopoCase,
    require_free_port,
    require_root_tools,
    to_floodlight_dpid,
    wait_for,
)

pytestmark = pytest.mark.integration

# топологии, которые запускаются под Floodlight; большие деревья только в unit-тестах
FLOODLIGHT_CASES = [
    case
    for case in TOPO_CASES
    if case.id in {"linear-k4", "linear-perf-k4", "tree-k2", "ring-n3-k3", "ring-n2-k2"}
]


# с запущенным снаружи Floodlight старые связи живут ещё до 35 с
LINK_DISCOVERY_TIMEOUT = 90


def switch_links(net: Mininet) -> set[frozenset[str]]:
    """Связи между коммутаторами в формате REST API Floodlight."""
    return {
        frozenset(
            (
                to_floodlight_dpid(link.intf1.node.dpid),
                to_floodlight_dpid(link.intf2.node.dpid),
            )
        )
        for link in net.links
        if link.intf1.node in net.switches and link.intf2.node in net.switches
    }


def iperf_mbits(result: str) -> float:
    value, unit = re.fullmatch(r"([\d.]+) ([KMG])bits/sec", result).groups()
    return float(value) * {"K": 1e-3, "M": 1.0, "G": 1e3}[unit]


@pytest.fixture(scope="module", params=FLOODLIGHT_CASES, ids=lambda case: case.id)
def floodlight_net(
    request: pytest.FixtureRequest,
    floodlight: Floodlight,
    openflow: str,
) -> Iterator[tuple[Mininet, TopoCase]]:
    """Сеть подключена к Floodlight, контроллер видит ровно её коммутаторы и связи.

    Одна сеть на топологию: все тесты с этой фикстурой идут на ней подряд.
    """
    from mininet.clean import cleanup

    require_root_tools()
    cleanup()
    floodlight.reset()
    case: TopoCase = request.param
    topo = case.build()
    if case.id.startswith("linear-perf"):
        from LinearTopoPerf import LinearTopo

        # без потерь, иначе pingAll недетерминирован
        topo = LinearTopo(k=case.params["k"], linkopts={"bw": 10.0, "delay": "5ms"})
    net = make_net(topo, floodlight.of, openflow, host=CPULimitedHost, link=TCLink)
    net.start()
    try:
        assert net.waitConnected(timeout=30), "коммутаторы не подключились к Floodlight"
        expected = {to_floodlight_dpid(sw.dpid) for sw in net.switches}
        assert wait_for(lambda: expected <= floodlight.switches(), 30), (
            f"Floodlight видит {floodlight.switches()}, ожидалось {expected}"
        )
        links = switch_links(net)
        assert wait_for(lambda: floodlight.links() == links, LINK_DISCOVERY_TIMEOUT), (
            f"LLDP: Floodlight видит {floodlight.links()}, ожидалось {links}"
        )
        announce_hosts(net)
        yield net, case
    finally:
        net.stop()
        cleanup()


def test_floodlight_sees_topology(
    floodlight_net: tuple[Mininet, TopoCase], floodlight: Floodlight
) -> None:
    net, case = floodlight_net
    assert floodlight.switches() >= {to_floodlight_dpid(sw.dpid) for sw in net.switches}
    links = switch_links(net)
    assert len(links) == case.switch_links
    assert floodlight.links() == links


def test_ping_all(floodlight_net: tuple[Mininet, TopoCase]) -> None:
    net, case = floodlight_net
    assert len(net.hosts) == case.hosts
    assert net.pingAll(timeout="1") == 0


def test_iperf_limited_by_bottleneck(floodlight_net: tuple[Mininet, TopoCase]) -> None:
    net, _ = floodlight_net
    first, last = net.hosts[0], net.hosts[-1]
    if first is last:
        pytest.skip("один хост")
    server, client = (iperf_mbits(r) for r in net.iperf((first, last), seconds=3))
    limits = [
        info["bw"] for _, _, info in net.topo.links(withInfo=True) if "bw" in info
    ]
    if not limits:
        assert client > 0 and server > 0
        return
    bottleneck = min(limits)
    for measured in (server, client):
        assert 0.5 * bottleneck < measured <= 1.05 * bottleneck


# ----------------------------------------------------------- scripts as is


def test_linear_script_default_controller(mininet_cleanup: None) -> None:
    from LinearTopo import simple_test

    # контроллер Mininet по умолчанию слушает тот же порт, что и Floodlight
    require_free_port(6653)

    assert simple_test(k=4) == 0


def test_ring_stp_without_controller(mininet_cleanup: None) -> None:
    from RingTopo import RingTopo, make_ring_net, wait_stp

    net = make_ring_net(RingTopo(n=4, k=2), controller=None)
    net.start()
    try:
        assert wait_stp(net, timeout=90), "STP не сошёлся"
        blocked = [
            intf.name
            for sw in net.switches
            for intf in sw.intfList()
            if intf.name != "lo"
            and sw.vsctl("get", "Port", intf.name, "status:stp_state")
            .strip()
            .strip('"')
            == "blocking"
        ]
        assert blocked, "в кольце должен быть заблокированный STP порт"
        assert net.pingAll(timeout="1") == 0
    finally:
        net.stop()
