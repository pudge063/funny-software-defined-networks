from __future__ import annotations

import json
import os
import pwd
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from mininet.topo import Topo

from common import DEFAULT_OPENFLOW, OPENFLOW_VERSIONS, ControllerAddr

INTEGRATION = "integration"


# ---------------------------------------------------------------- topologies


@dataclass(frozen=True)
class TopoCase:
    """Топология и то, что из неё должно получиться."""

    id: str
    factory: Callable[[], Topo]
    hosts: int
    switches: int
    links: int
    switch_links: int
    params: dict[str, Any] = field(default_factory=dict)

    def build(self) -> Topo:
        return self.factory()


def _linear(k: int) -> TopoCase:
    from LinearTopo import LinearTopo

    return TopoCase(
        f"linear-k{k}", lambda: LinearTopo(k=k), k, k, 2 * k - 1, k - 1, {"k": k}
    )


def _linear_perf(k: int) -> TopoCase:
    from LinearTopoPerf import LinearTopo

    return TopoCase(
        f"linear-perf-k{k}", lambda: LinearTopo(k=k), k, k, 2 * k - 1, k - 1, {"k": k}
    )


def _tree(k: int) -> TopoCase:
    from TreeTopo import AGGREGATION_LINKOPTS, CORE_LINKOPTS, EDGE_LINKOPTS, CustomTopo

    hosts, switches = k**3, 1 + k + k**2
    return TopoCase(
        f"tree-k{k}",
        lambda: CustomTopo(
            CORE_LINKOPTS, AGGREGATION_LINKOPTS, EDGE_LINKOPTS, fanout=k
        ),
        hosts,
        switches,
        hosts + switches - 1,
        switches - 1,
        {"fanout": k},
    )


def _ring(n: int, k: int) -> TopoCase:
    from RingTopo import RingTopo

    ring_links = n if n > 2 else n - 1
    return TopoCase(
        f"ring-n{n}-k{k}",
        lambda: RingTopo(
            n=n,
            k=k,
            ringopts={"bw": 20.0, "delay": "10ms"},
            hostopts={"bw": 10.0, "delay": "1ms"},
        ),
        n * k,
        n,
        n * k + ring_links,
        ring_links,
        {"n": n, "k": k},
    )


TOPO_CASES: list[TopoCase] = [
    _linear(1),
    _linear(4),
    _linear_perf(4),
    _tree(1),
    _tree(2),
    _tree(3),
    _ring(1, 2),
    _ring(2, 2),
    _ring(3, 3),
    _ring(5, 1),
]


@pytest.fixture(params=TOPO_CASES, ids=lambda case: case.id)
def topo_case(request: pytest.FixtureRequest) -> TopoCase:
    return request.param


@pytest.fixture
def topo(topo_case: TopoCase) -> Topo:
    return topo_case.build()


# ---------------------------------------------------------------- integration


def _invoking_user_home() -> Path:
    """Домашний каталог пользователя, а не root, когда тесты идут через sudo."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return Path(pwd.getpwnam(sudo_user).pw_dir)
    return Path.home()


def _port_open(host: str, port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for(
    predicate: Callable[[], bool], timeout: float, interval: float = 1.0
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def to_floodlight_dpid(dpid: str) -> str:
    """'0000000000000100' -> '00:00:00:00:00:00:01:00'."""
    dpid = dpid.rjust(16, "0")
    return ":".join(dpid[i : i + 2] for i in range(0, 16, 2))


@dataclass
class Floodlight:
    """Клиент REST API Floodlight и, если тесты запустили его сами, процесс."""

    of: ControllerAddr
    rest_url: str
    command: list[str] | None = None  # None: контроллер запущен кем-то другим
    cwd: Path | None = None
    log_path: Path | None = None
    proc: subprocess.Popen[bytes] | None = field(default=None, repr=False)

    def get(self, path: str) -> Any:
        with urllib.request.urlopen(f"{self.rest_url}{path}", timeout=5) as resp:
            return json.load(resp)

    def alive(self) -> bool:
        try:
            self.get("/wm/core/controller/switches/json")
        except (OSError, urllib.error.URLError, ValueError):
            return False
        return True

    def switches(self) -> set[str]:
        return {
            sw["switchDPID"] for sw in self.get("/wm/core/controller/switches/json")
        }

    def links(self) -> set[frozenset[str]]:
        return {
            frozenset((link["src-switch"], link["dst-switch"]))
            for link in self.get("/wm/topology/links/json")
        }

    def start(self) -> None:
        assert self.command is not None and self.log_path is not None
        with self.log_path.open("a") as log:
            self.proc = subprocess.Popen(
                self.command, cwd=self.cwd, stdout=log, stderr=subprocess.STDOUT
            )
        proc = self.proc
        if not wait_for(lambda: proc.poll() is not None or self.alive(), 90):
            pytest.fail(f"Floodlight не поднялся за 90 с, лог: {self.log_path}")
        if proc.poll() is not None:
            pytest.fail(
                f"Floodlight завершился с кодом {proc.returncode}, лог: {self.log_path}"
            )

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc = None
        wait_for(lambda: not _port_open(self.of.ip, self.of.port), 15, 0.2)

    def reset(self) -> None:
        """Перезапустить контроллер перед новой топологией.

        Floodlight 1.2 хранит связи и устройства прошлой сети; когда коммутаторы
        с теми же DPID быстро переподключаются, маршруты строятся по устаревшим
        данным и часть хостов недоступна. Чужой контроллер не трогаем.
        """
        if self.command is not None:
            self.stop()
            self.start()


def require_free_port(port: int, host: str = "127.0.0.1") -> None:
    if _port_open(host, port):
        pytest.skip(f"порт {port} занят (запущен Floodlight?)")


def require_root_tools() -> None:
    if os.geteuid() != 0:
        pytest.skip(
            "Mininet нужен root: запустите `make test` или `sudo .venv/bin/pytest`"
        )
    for tool in ("ovs-vsctl", "iperf", "mn"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} не найден в PATH")


@pytest.fixture(scope="session")
def floodlight(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Floodlight]:
    """Запустить Floodlight (или переиспользовать уже запущенный)."""
    require_root_tools()
    client = Floodlight(
        ControllerAddr(os.environ.get("FLOODLIGHT_HOST", "127.0.0.1"), 6653),
        os.environ.get("FLOODLIGHT_REST", "http://127.0.0.1:8080"),
    )
    if client.alive():
        yield client
        return
    if _port_open(client.of.ip, client.of.port):
        pytest.fail(f"порт {client.of} занят, но REST API Floodlight не отвечает")

    jar = Path(
        os.environ.get(
            "FLOODLIGHT_JAR", _invoking_user_home() / "floodlight/target/floodlight.jar"
        )
    )
    if not jar.is_file():
        pytest.skip(f"не найден {jar}, задайте FLOODLIGHT_JAR")
    java = shutil.which("java")
    if java is None:
        pytest.skip("java не найдена в PATH")

    client.command = [java, "-jar", str(jar)]
    # cwd = корень репозитория floodlight: там лежат конфиги и каталог для логов
    client.cwd = jar.parent.parent
    client.log_path = tmp_path_factory.mktemp("floodlight") / "floodlight.log"
    client.start()
    try:
        yield client
    finally:
        client.stop()


@pytest.fixture
def fresh_floodlight(floodlight: Floodlight) -> Floodlight:
    floodlight.reset()
    return floodlight


@pytest.fixture(scope="session")
def openflow() -> str:
    """Версия OpenFlow для коммутаторов под Floodlight (env OPENFLOW)."""
    version = os.environ.get("OPENFLOW", DEFAULT_OPENFLOW)
    if version not in OPENFLOW_VERSIONS:
        pytest.fail(f"OPENFLOW={version!r}, ожидалось одно из {OPENFLOW_VERSIONS}")
    return version


@pytest.fixture
def mininet_cleanup() -> Iterator[None]:
    """Убрать остатки предыдущих запусков Mininet до и после теста."""
    require_root_tools()
    from mininet.clean import cleanup

    cleanup()
    yield
    cleanup()


# ---------------------------------------------------------------- ordering


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Порядок: тесты на фикстурах, Mininet без Floodlight, Mininet с Floodlight.

    Floodlight живёт всю сессию и занимает порт 6653, который нужен
    контроллеру Mininet по умолчанию, поэтому тесты с ним идут последними."""

    def stage(item: pytest.Item) -> int:
        if item.get_closest_marker(INTEGRATION) is None:
            return 0
        return 2 if "floodlight" in getattr(item, "fixturenames", ()) else 1

    items.sort(key=stage)


_unit_failed = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    report = yield
    if report.failed and item.get_closest_marker(INTEGRATION) is None:
        item.session.stash[_unit_failed] = True
    return report


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker(INTEGRATION) and item.session.stash.get(
        _unit_failed, False
    ):
        pytest.skip("unit-тесты упали, integration не запускаем")
