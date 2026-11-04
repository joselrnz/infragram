"""An importer rerun cannot undo the review its catalog has had.

The on-premises catalog holds 845 3D items another tool installed beside the
upstream node set; the IBM pack lost three fragment icons in review; the
brand logos ship 17 reviewed brands out of thousands, with a hand-written
families.json beside them. Each importer once rebuilt its catalog from
upstream alone, so a rerun would have undone all of that without a word.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from infragram.paths import repo_root

ROOT = repo_root()
sys.path.insert(0, str(ROOT / "scripts"))

from lib.catalog_guard import catalog_ids, refusal  # noqa: E402

ONPREM = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors/onprem/catalog.json"


def _catalog(tmp_path: Path, ids: list[str]) -> Path:
    path = tmp_path / "pack" / "catalog.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"icons": [{"id": icon} for icon in ids]}), encoding="utf-8")
    return path


def test_the_same_ids_pass_and_a_change_is_refused(tmp_path) -> None:
    catalog = _catalog(tmp_path, ["a", "b", "c"])
    assert refusal(catalog, ["c", "b", "a"]) is None
    dropped = refusal(catalog, ["a", "b"])
    assert dropped and "drop 1 icons" in dropped and "(c)" in dropped
    added = refusal(catalog, ["a", "b", "c", "fragment"])
    assert added and "add 1 it does not (fragment)" in added
    assert refusal(catalog, ["a"], force=True) is None
    assert refusal(tmp_path / "none.json", ["a"]) is None, "a first import has nothing to undo"


def test_the_onprem_importer_answers_only_for_its_own_ids() -> None:
    def upstream(icon: str) -> bool:
        return not icon.startswith("iso-")

    everything = catalog_ids(ONPREM)
    own = catalog_ids(ONPREM, upstream)
    assert len(everything - own) >= 845, "the 3D items are not the importer's"
    assert refusal(ONPREM, sorted(own), owned=upstream) is None
    assert refusal(ONPREM, sorted(own)[1:], owned=upstream) is not None


def _brand_importer(monkeypatch, tmp_path: Path):
    spec = importlib.util.spec_from_file_location(
        "infragram_brand_icons", ROOT / "scripts" / "importers" / "brand-icons.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dest = tmp_path / "logos"
    dest.mkdir()
    (dest / "families.json").write_text('{"curated": true}', encoding="utf-8")
    (dest / "README.md").write_text("written by hand\n", encoding="utf-8")
    (dest / "catalog.json").write_text(
        json.dumps({"icons": [{"id": "aws", "name": "AWS"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(module, "DEST_ROOT", dest)
    source = tmp_path / "vault"
    thesvg = source / "multi-cloud" / "thesvg"
    (thesvg / "src" / "data").mkdir(parents=True)
    index = []
    for slug in ("aws", "nginx", "someother"):
        folder = thesvg / "public" / "icons" / slug
        folder.mkdir(parents=True)
        (folder / "default.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>', encoding="utf-8"
        )
        index.append({"slug": slug, "title": slug, "license": "MIT", "collection": "brands"})
    (thesvg / "src" / "data" / "icons.json").write_text(json.dumps(index), encoding="utf-8")
    return module, source, dest


@pytest.mark.parametrize(
    ("extra", "expected"),
    [([], ["aws"]), (["--add", "nginx"], ["aws", "nginx"])],
)
def test_the_brand_importer_refreshes_what_ships(monkeypatch, tmp_path, extra, expected) -> None:
    module, source, dest = _brand_importer(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["brand-icons.py", "--source-root", str(source), *extra])
    assert module.main() == 0
    catalog = json.loads((dest / "catalog.json").read_text(encoding="utf-8"))
    assert [icon["id"] for icon in catalog["icons"]] == expected
    assert (dest / "families.json").read_text(encoding="utf-8") == '{"curated": true}'
    assert (dest / "README.md").is_file()
    assert not (dest / "someother").exists()
