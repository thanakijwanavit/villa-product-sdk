"""Offline checks for the user-facing docs (vps-0we). Standard library only; no AWS."""
import ast
import configparser
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
CONTRIBUTING = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
INDEX_NB = json.loads((ROOT / "index.ipynb").read_text(encoding="utf-8"))


def public_sdk_methods():
    """Public methods of ProductSdk in products.py, including those attached with @add_method."""
    tree = ast.parse((ROOT / "villaProductSdk" / "products.py").read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ProductSdk":
            names |= {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
        if isinstance(node, ast.FunctionDef) and any(
            isinstance(d, ast.Call) and getattr(d.func, "id", "") == "add_method"
            and any(getattr(a, "id", "") == "ProductSdk" for a in d.args)
            for d in node.decorator_list
        ):
            names.add(node.name)
    return {n for n in names if not n.startswith("_")}


def test_found_the_sdk_methods():
    assert {"querySingleProduct", "queryList", "allQuery", "updateWithS3", "syncS3"} <= public_sdk_methods()


def test_readme_documents_every_public_method():
    missing = [m for m in sorted(public_sdk_methods()) if f"`{m}(" not in README and f".{m}(" not in README]
    assert not missing, f"README does not document: {missing}"


def test_readme_has_required_sections():
    for heading in ["## Install", "### Supported Python", "## Authentication", "## Stages",
                    "## Example (dev stage)", "## API reference", "## Security", "## Known issues"]:
        assert heading in README, heading


def test_readme_is_generated_from_index_notebook():
    """README.md must be rebuilt from index.ipynb: every markdown line in the notebook appears in it."""
    for cell in INDEX_NB["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        for line in "".join(cell["source"]).splitlines():
            if line.strip() and not line.startswith("# "):  # the H1 becomes front matter
                assert line in README, f"README is stale; rebuild with nbdev_build_docs: {line!r}"


def test_example_uses_dev_stage_and_no_inline_keys():
    example = README.split("## Example (dev stage)", 1)[1].split("\n## ", 1)[0]
    assert 'branch="dev-manual"' in example
    assert "user=" not in example and "pw=" not in example


AWS_KEY_ID = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
AWS_SECRET = re.compile(r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+=])")


def test_no_credentials_or_personal_paths_in_docs():
    texts = {"README.md": README, "CHANGELOG.md": CHANGELOG, "CONTRIBUTING.md": CONTRIBUTING,
             "index.ipynb": (ROOT / "index.ipynb").read_text(encoding="utf-8")}
    for name, text in texts.items():
        assert not AWS_KEY_ID.search(text), f"AWS access key id in {name}"
        assert not AWS_SECRET.search(text), f"40-character secret-like string in {name}"
        assert "/Users/" not in text, f"personal path in {name}"
        assert not re.search(r"pickle\.(dump|load)", text), f"credential pickle in {name}"


def test_changelog_names_released_and_repo_versions():
    cfg = configparser.ConfigParser(delimiters=["="])
    cfg.read(ROOT / "settings.ini")
    assert cfg["DEFAULT"]["version"] in CHANGELOG
    assert "## 0.0.20" in CHANGELOG
    assert CHANGELOG.index("## Unreleased") < CHANGELOG.index("## 0.0.20")


def test_contributing_matches_layout():
    assert "nbs folder" not in CONTRIBUTING
    assert "nbdev_install_git_hooks" in CONTRIBUTING
    for nb in re.findall(r"`([\w-]+\.ipynb)`", CONTRIBUTING):
        assert (ROOT / nb).exists(), f"CONTRIBUTING names a missing notebook: {nb}"
    cfg = configparser.ConfigParser(delimiters=["="])
    cfg.read(ROOT / "settings.ini")
    assert cfg["DEFAULT"]["nbs_path"] == "."
