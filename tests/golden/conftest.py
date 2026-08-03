"""Golden File test infrastructure: auto-pair fixture <-> expected."""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXPECTED_DIR = Path(__file__).parent / "expected"


def discover_cases():
    """Scan fixtures/, return cases with _verified=true expected JSON."""
    cases = []
    for f in sorted(FIXTURES_DIR.iterdir()):
        if not f.is_file():
            continue
        exp = EXPECTED_DIR / f"{f.stem}.json"
        if not exp.exists():
            continue
        data = json.loads(exp.read_text(encoding="utf-8"))
        if not data.get("_verified", False):
            continue
        cases.append((f.stem, f, exp))
    return cases


@pytest.fixture(params=discover_cases(), ids=lambda c: c[0])
def golden_case(request):
    stem, fixture_path, expected_path = request.param
    with open(expected_path, encoding="utf-8") as fp:
        expected = json.load(fp)
    raw_bytes = fixture_path.read_bytes()
    ext = fixture_path.suffix.lower()
    return {
        "stem": stem,
        "raw_bytes": raw_bytes,
        "ext": ext,
        "expected": expected,
        "fixture_path": fixture_path,
    }
