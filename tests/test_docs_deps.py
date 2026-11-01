"""vps-tzc: the nbdev v1 Jekyll scaffolding in docs/ pinned nokogiri 1.10.8, activesupport 6.0.3.2 and
github-pages 207, all with published advisories. It is removed (the docs move to README/CHANGELOG, vps-0we):
docs/Gemfile, Gemfile.lock, _config.yml, _includes, _layouts, and the Makefile's docs_serve target. If a
Gemfile.lock comes back, it must not bring those versions back."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_PINS = re.compile(r"^    (nokogiri \(1\.1[0-5]\.|activesupport \(6\.0\.|github-pages \(20[0-9]\))[^\n]*", re.M)


def old_pins(lock_text: str) -> list[str]:
    return [m.group(0).strip() for m in OLD_PINS.finditer(lock_text)]


def test_docs_gemfile_lock_has_no_vulnerable_pins():
    lock = ROOT / "docs" / "Gemfile.lock"
    assert not lock.exists() or old_pins(lock.read_text()) == [], old_pins(lock.read_text())


def test_nothing_builds_or_serves_the_jekyll_site():
    for name in ("Makefile", "build.sh"):
        path = ROOT / name
        if path.exists():
            assert not re.search(r"\b(bundle|jekyll)\b", path.read_text(), re.I), name


def test_the_pin_check_catches_the_old_versions():
    # the removed lock's lines, so this test is not vacuous now that the file is gone
    removed = "    activesupport (6.0.3.2)\n    github-pages (207)\n    nokogiri (1.10.8)\n"
    assert old_pins(removed) == ["activesupport (6.0.3.2)", "github-pages (207)", "nokogiri (1.10.8)"]
    current = "    activesupport (7.1.5)\n    github-pages (232)\n    nokogiri (1.16.7)\n"
    assert old_pins(current) == []
