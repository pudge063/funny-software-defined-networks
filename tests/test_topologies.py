"""Проверки структуры топологий без запуска Mininet (root не нужен)."""

from __future__ import annotations

import argparse
import re
from collections import deque

import pytest
from mininet.topo import Topo

from common import DEFAULT_CONTROLLER, ControllerAddr, parse_controller, positive_int
from conftest import TopoCase

DELAY_RE = re.compile(r"^\d+(\.\d+)?(us|ms|s)$")
LINKOPT_TYPES: dict[str, type | tuple[type, ...]] = {
    "bw": (int, float),
    "delay": str,
    "jitter": str,
    "loss": (int, float),
    "max_queue_size": int,
    "use_htb": bool,
}


def neighbours(topo: Topo, node: str) -> list[str]:
    return [dst for src, dst in topo.links() if src == node] + [
        src for src, dst in topo.links() if dst == node
    ]


def switch_links(topo: Topo) -> list[tuple[str, str]]:
    return [(a, b) for a, b in topo.links() if topo.isSwitch(a) and topo.isSwitch(b)]


# ------------------------------------------------------------ all topologies


def test_node_and_link_counts(topo: Topo, topo_case: TopoCase) -> None:
    assert len(topo.hosts()) == topo_case.hosts
    assert len(topo.switches()) == topo_case.switches
    assert len(topo.links()) == topo_case.links
    assert len(switch_links(topo)) == topo_case.switch_links


def test_names_are_strings_and_unique(topo: Topo) -> None:
    nodes = topo.nodes()
    assert all(isinstance(name, str) for name in nodes)
    assert len(set(nodes)) == len(nodes)


def test_every_host_has_single_uplink_to_switch(topo: Topo) -> None:
    for host in topo.hosts():
        (uplink,) = neighbours(topo, host)
        assert topo.isSwitch(uplink)


def test_graph_is_connected(topo: Topo) -> None:
    nodes = topo.nodes()
    seen, queue = {nodes[0]}, deque([nodes[0]])
    while queue:
        for nxt in neighbours(topo, queue.popleft()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    assert seen == set(nodes)


def test_no_self_loops_or_duplicate_links(topo: Topo) -> None:
    pairs = [frozenset(link) for link in topo.links()]
    assert all(len(pair) == 2 for pair in pairs)
    assert len(set(pairs)) == len(pairs)


def test_link_options_have_mininet_types(topo: Topo) -> None:
    for src, dst in topo.links():
        info = topo.linkInfo(src, dst)
        for key, expected in LINKOPT_TYPES.items():
            if key in info:
                assert isinstance(info[key], expected), (src, dst, key, info[key])
        if "delay" in info:
            assert DELAY_RE.match(info["delay"]), info["delay"]
        if "loss" in info:
            assert 0 <= info["loss"] <= 100


def test_datapath_ids_are_unique(topo: Topo) -> None:
    """Явный dpid или число из имени коммутатора (так его выводит Mininet)."""
    dpids = []
    for switch in topo.switches():
        dpid = topo.nodeInfo(switch).get("dpid")
        if dpid is None:
            digits = re.findall(r"\d+", switch)
            assert digits, switch
            dpids.append(int(digits[0]))
        else:
            assert isinstance(dpid, str) and re.fullmatch(r"[0-9a-f]{1,16}", dpid)
            dpids.append(int(dpid, 16))
    assert len(set(dpids)) == len(dpids)


# ------------------------------------------------------------ concrete shapes


def test_linear_is_a_chain() -> None:
    from LinearTopo import LinearTopo

    topo = LinearTopo(k=4)
    assert {frozenset(link) for link in switch_links(topo)} == {
        frozenset(("s1", "s2")),
        frozenset(("s2", "s3")),
        frozenset(("s3", "s4")),
    }
    assert topo.k == 4


def test_linear_perf_limits() -> None:
    from LinearTopoPerf import DEFAULT_LINKOPTS, LinearTopo

    k = 4
    topo = LinearTopo(k=k)
    cpu = [topo.nodeInfo(h)["cpu"] for h in topo.hosts()]
    assert cpu == [pytest.approx(0.5 / k)] * k
    assert sum(cpu) == pytest.approx(0.5)
    for src, dst in topo.links():
        info = topo.linkInfo(src, dst)
        assert {key: info[key] for key in DEFAULT_LINKOPTS} == DEFAULT_LINKOPTS


def test_linear_perf_custom_linkopts() -> None:
    from LinearTopoPerf import LinearTopo

    topo = LinearTopo(k=2, linkopts={"bw": 5.0, "delay": "1ms"})
    for src, dst in topo.links():
        info = topo.linkInfo(src, dst)
        assert (info["bw"], info["delay"]) == (5.0, "1ms")
        assert "loss" not in info


@pytest.mark.parametrize("fanout", [1, 2, 3])
def test_tree_levels(fanout: int) -> None:
    from TreeTopo import AGGREGATION_LINKOPTS, CORE_LINKOPTS, EDGE_LINKOPTS, CustomTopo

    topo = CustomTopo(CORE_LINKOPTS, AGGREGATION_LINKOPTS, EDGE_LINKOPTS, fanout=fanout)
    by_prefix = {
        prefix: [s for s in topo.switches() if re.fullmatch(rf"{prefix}\d+", s)]
        for prefix in ("cs", "as", "es")
    }
    assert [len(v) for v in by_prefix.values()] == [1, fanout, fanout**2]

    level_opts = {"cs": CORE_LINKOPTS, "as": AGGREGATION_LINKOPTS, "es": EDGE_LINKOPTS}
    child_level = {"cs": "as", "as": "es", "es": "h"}
    for src, dst in topo.links():
        info = topo.linkInfo(src, dst)
        # addLink(child, parent): node1 - потомок, node2 - родитель
        child, parent = info["node1"], info["node2"]
        level = parent.rstrip("0123456789")
        assert child.startswith(child_level[level])
        assert {key: info[key] for key in level_opts[level]} == level_opts[level]

    for switch in topo.switches():
        uplinks = 0 if switch.startswith("cs") else 1
        assert len(neighbours(topo, switch)) == fanout + uplinks


def test_tree_dpids_encode_level() -> None:
    from TreeTopo import CustomTopo, dpid

    assert dpid(0x200, 3) == "203"
    topo = CustomTopo(fanout=2)
    dpids = {s: topo.nodeInfo(s)["dpid"] for s in topo.switches()}
    assert dpids["cs1"] == "100"
    assert dpids["as2"] == "202"
    assert dpids["es4"] == "304"


@pytest.mark.parametrize(("n", "k"), [(3, 3), (4, 2), (6, 1)])
def test_ring_is_a_cycle(n: int, k: int) -> None:
    from RingTopo import RingTopo

    topo = RingTopo(n=n, k=k)
    for i in range(1, n + 1):
        switch = f"s{i}"
        ring_peers = {p for p in neighbours(topo, switch) if topo.isSwitch(p)}
        assert ring_peers == {f"s{(i - 2) % n + 1}", f"s{i % n + 1}"}
        hosts = sorted(h for h in neighbours(topo, switch) if not topo.isSwitch(h))
        assert hosts == sorted(f"h{(i - 1) * k + j}" for j in range(1, k + 1))


def test_ring_link_options_split_by_role() -> None:
    from RingTopo import RingTopo

    ringopts = {"bw": 20.0, "delay": "10ms"}
    hostopts = {"bw": 10.0, "delay": "1ms"}
    topo = RingTopo(n=3, k=2, ringopts=ringopts, hostopts=hostopts)
    for src, dst in topo.links():
        info = topo.linkInfo(src, dst)
        expected = ringopts if topo.isSwitch(src) and topo.isSwitch(dst) else hostopts
        assert {k: info[k] for k in expected} == expected


# ------------------------------------------------------------ helpers / CLI


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("127.0.0.1:6653", ControllerAddr("127.0.0.1", 6653)),
        ("10.0.0.1:6633", ControllerAddr("10.0.0.1", 6633)),
        ("::1:6653", ControllerAddr("::1", 6653)),
    ],
)
def test_parse_controller(value: str, expected: ControllerAddr) -> None:
    addr = parse_controller(value)
    assert addr == expected
    assert isinstance(addr.port, int)


@pytest.mark.parametrize("value", ["127.0.0.1", ":6653", "host:port", "h:0", "h:70000"])
def test_parse_controller_rejects(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_controller(value)


def test_default_controller() -> None:
    assert str(DEFAULT_CONTROLLER) == "127.0.0.1:6653"


def test_positive_int() -> None:
    assert positive_int("3") == 3
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
    with pytest.raises(ValueError):
        positive_int("two")
