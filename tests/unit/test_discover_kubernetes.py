"""A live Kubernetes cluster to a diagram: ``discover:kubernetes``.

kubectl is replayed from ``tests/fixtures/estate/discover/kubernetes.json``,
a small shop namespace, so what is held here is:

- every call only reads (``config view``, ``get``), one kind at a time, and a
  kind the account may not list is a note while the rest is drawn;
- what a controller made is folded into it: a Deployment's ReplicaSets and
  Pods, a CronJob's Jobs and their Pods, a StatefulSet's claims from its
  volume claim templates; the system namespaces and the API server's own
  Service are left out unless asked;
- the wires are the ones the objects name: ingress rules to services,
  selectors to workloads, claims mounted, autoscaler targets;
- each Service's app is a workload frame, and the drawing composes to a
  picture the checker passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infragram.estate import Box, Card, write_spec
from infragram.estate.discover import CallError, DiscoveryError
from infragram.estate.discover.kubernetes import discover_kubernetes, draw_cluster
from infragram.paths import repo_root

RECORDED = json.loads(
    (repo_root() / "tests/fixtures/estate/discover/kubernetes.json").read_text(encoding="utf-8")
)


class Kubectl:
    """kubectl answering from the recording, remembering what it was asked."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]):
        self.calls.append(list(args))
        if args[:2] == ["config", "view"]:
            return RECORDED["config"]
        if args[1] in RECORDED["forbidden"]:
            raise CallError(f"kubectl get {args[1]}", "forbidden")
        return {"kind": "List", "items": RECORDED["kinds"].get(args[1], [])}


def _drawn(include_system: bool = False):
    kubectl = Kubectl()
    estate = discover_kubernetes(runner=kubectl)
    return kubectl, estate, draw_cluster(estate, include_system=include_system)


def test_only_reads_and_a_forbidden_kind_is_a_note() -> None:
    kubectl, estate, drawing = _drawn()
    assert {call[0] for call in kubectl.calls} == {"config", "get"}
    assert all("--all-namespaces" in call for call in kubectl.calls if call[0] == "get")
    assert estate.title == "Kubernetes cluster shop-prod"
    assert "daemonsets not read: forbidden" in drawing.notes


def test_what_a_controller_made_is_folded_into_it() -> None:
    _, _, drawing = _drawn()
    assert drawing.folded["Pod/shop/web-7d9f-a1"] == "folded into Deployment/shop/web"
    assert drawing.folded["ReplicaSet/shop/web-7d9f"] == "folded into Deployment/shop/web"
    assert drawing.folded["Pod/shop/nightly-report-29311-x"] == (
        "folded into CronJob/shop/nightly-report"
    )
    assert drawing.folded["PersistentVolumeClaim/shop/data-db-1"] == (
        "folded into StatefulSet/shop/db"
    )
    assert "Pod/shop/debug" in drawing.drawn, "a bare pod is drawn"
    assert drawing.left_out["Service/default/kubernetes"].startswith("the API server")
    assert "Deployment/kube-system/coredns" in drawing.left_out
    _, _, everything = _drawn(include_system=True)
    assert "Deployment/kube-system/coredns" in everything.drawn


def test_the_wires_are_the_ones_the_objects_name() -> None:
    _, _, drawing = _drawn()
    wires = {(wire.source, wire.target): (wire.label, wire.dashed) for wire in drawing.wires}
    assert wires == {
        ("Ingress/shop/shop", "Service/shop/web"): ("shop.example.com/", False),
        ("Ingress/shop/shop", "Service/shop/api"): ("shop.example.com/api", False),
        ("Service/shop/web", "Deployment/shop/web"): (":8080", False),
        ("Service/shop/api", "Deployment/shop/api"): (":9000", False),
        ("Service/shop/db", "StatefulSet/shop/db"): (":5432", False),
        ("Deployment/shop/api", "PersistentVolumeClaim/shop/uploads"): ("", False),
        ("HorizontalPodAutoscaler/shop/api", "Deployment/shop/api"): ("scales", True),
    }


def test_each_app_is_a_frame_in_its_namespace() -> None:
    _, _, drawing = _drawn()
    (cluster,) = drawing.roots
    (shop,) = cluster.children
    assert (cluster.kind, shop.kind, shop.caption) == ("cluster", "namespace", "shop")
    apps = {
        child.caption: [card.key for card in child.children]
        for child in shop.children
        if isinstance(child, Box)
    }
    assert apps["api"] == [
        "Service/shop/api",
        "Deployment/shop/api",
        "HorizontalPodAutoscaler/shop/api",
        "PersistentVolumeClaim/shop/uploads",
    ]
    loose = [child.key for child in shop.children if isinstance(child, Card)]
    assert loose == ["Ingress/shop/shop", "CronJob/shop/nightly-report", "Pod/shop/debug"]


def test_no_context_is_refused() -> None:
    with pytest.raises(DiscoveryError, match="--context"):
        discover_kubernetes(runner=lambda args: {} if args[0] == "config" else None)


def test_the_command_writes_a_drawing_that_composes(tmp_path: Path, monkeypatch, capsys) -> None:
    from infragram.cli.user import import_estate
    from infragram.cli.user.checker import checker
    from infragram.cli.user.compose import project_from_spec
    from infragram.estate.discover import kubernetes
    from infragram.exports import render_project_svg

    monkeypatch.setattr(kubernetes, "cli_runner", lambda program: Kubectl())
    argv = ["--namespace", "shop", "--no-export", "--output-dir", str(tmp_path)]
    assert import_estate.discover_kubernetes(argv) == 0, capsys.readouterr().err
    (spec,) = tmp_path.glob("*.py")
    text = spec.read_text(encoding="utf-8")
    assert "infragram discover:kubernetes --namespace shop" in text
    assert "kubernetes_frames.Workload('api').row()" in text
    project = project_from_spec(spec)
    picture = tmp_path / "cluster.svg"
    picture.write_text(render_project_svg(project), encoding="utf-8")
    ok, message = checker().check_path(picture)
    assert ok, message
    assert write_spec  # the same writer every import uses
