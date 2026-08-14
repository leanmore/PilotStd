#!/usr/bin/env python3
"""Generate Golden File test scaffolding from raw crawler output.

Stratified sampling across file types, optional parser pre-fill,
and manifest tracking for traceability back to source files.
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
from datetime import date
from pathlib import Path

DEFAULT_TARGET = "tests/golden"
DEFAULT_SAMPLE = 5
MAX_FILE_MB = 50
SUPPORTED_EXT = {".html", ".htm", ".pdf", ".doc", ".docx", ".wps",
                 ".xls", ".xlsx", ".et"}


def discover_files(source_dir: Path, allowed_ext: set[str]) -> tuple[dict, dict]:
    """递归扫描 source_dir，按扩展名分组，跳过空文件及超大文件。"""
    # 使用递归扫描；按大小和扩展名过滤
    grouped: dict[str, list[Path]] = {}
    skipped = {"empty": 0, "too_large": 0, "unsupported": 0}
    max_bytes = MAX_FILE_MB * 1024 * 1024

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in allowed_ext:
            skipped["unsupported"] += 1
            continue
        size = path.stat().st_size
        if size == 0:
            skipped["empty"] += 1
            continue
        if size > max_bytes:
            skipped["too_large"] += 1
            continue
        grouped.setdefault(ext, []).append(path)

    return grouped, skipped


def sample_files(grouped: dict, sample_size: int, strategy: str) -> list[tuple[Path, str]]:
    """分层抽样：diverse（按大小分桶），random 或 largest-first。"""
    # 策略：分入3个大小桶，从每桶均匀选取
    selected: list[tuple[Path, str]] = []

    for ext, files in sorted(grouped.items()):
        random.shuffle(files)
        n = min(sample_size, len(files))

        if strategy == "diverse" and len(files) >= sample_size * 2:
            files_sorted = sorted(files, key=lambda p: p.stat().st_size)
            chunk = max(1, len(files_sorted) // 3)
            buckets = [files_sorted[:chunk],
                       files_sorted[chunk:chunk * 2],
                       files_sorted[chunk * 2:]]
            per_bucket = max(1, n // 3)
            picked = []
            for bucket in buckets:
                picked.extend(random.sample(bucket, min(per_bucket, len(bucket))))
            remaining = [f for f in files_sorted if f not in picked]
            while len(picked) < n and remaining:
                picked.append(remaining.pop())
            selected.extend((p, ext) for p in picked[:n])
        elif strategy == "largest":
            files_sorted = sorted(files, key=lambda p: p.stat().st_size, reverse=True)
            selected.extend((p, ext) for p in files_sorted[:n])
        else:
            selected.extend((p, ext) for p in files[:n])

    return selected


def make_fixture_name(path: Path, ext: str, index: int) -> str:
    """生成可读且唯一的固件文件名，含内容哈希后缀。"""
    h = hashlib.md5(path.read_bytes()).hexdigest()[:4]
    stem = path.stem[:40].replace(" ", "_").replace("/", "_")
    return f"{ext.lstrip('.')}_{index:03d}_{stem}_{h}{ext}"


def run_parser(fixture_path: Path, ext: str) -> dict:
    """对固件运行 parse_announcement_detail，返回清理后的 dict 结果。"""
    try:
        from pilotstd.announcement.parser import parse_announcement_detail
    except ImportError as e:
        return {"_error": f"import failed: {e}", "items": [], "meta": {}}

    raw = fixture_path.read_bytes()

    # 根据文件类型路由：网页走参数，其他走附件流程
    try:
        if ext in (".html", ".htm"):
            html = raw.decode("utf-8", errors="replace")
            items, meta = parse_announcement_detail(html=html)
        else:
            items, meta = parse_announcement_detail(
                html="<html><body></body></html>",
                attachment_bytes=raw,
                attachment_filename=fixture_path.name,
            )
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}", "items": [], "meta": {}}

    def _clean(obj):
        """递归将非 JSON 可序列化值转换为基础类型。"""
        if isinstance(obj, list):
            return [_clean(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if not isinstance(obj, (str, int, float, bool, type(None))):
            return str(obj)
        return obj

    return {"items": _clean(items), "meta": _clean(meta)}


def build_skeleton(ext: str) -> dict:
    """返回空 expected.json 骨架，供人工标注使用。"""
    return {
        "_source_ext": ext,
        "_verified": False,
        "_notes": "fill in items and meta manually, then set _verified=true",
        "items": [{
            "std_code": "e.g. GB/T 12345-2024",
            "std_name": "standard name here",
            "publish_date": "YYYY-MM-DD or null",
            "implementation_date": "YYYY-MM-DD or null",
            "replaced_by": None,
            "status": "active/obsolete/upcoming",
        }],
        "meta": {"title": "announcement title", "publish_date": "YYYY-MM-DD"},
    }


def _print_scan_summary(grouped: dict, skipped: dict) -> int:
    """打印扫描结果，返回文件总数。"""
    total = sum(len(v) for v in grouped.values())
    print(f"  {total} files in {len(grouped)} types")
    for ext, files in sorted(grouped.items()):
        print(f"    {ext}: {len(files)}")
    if any(skipped.values()):
        print(f"  skipped: empty={skipped['empty']} "
              f"large={skipped['too_large']} other={skipped['unsupported']}")
    return total


def _generate_expected(selected: list, args, fixtures_dir: Path,
                       expected_dir: Path) -> list:
    """复制固件并生成预期 JSON，返回清单列表。"""
    ext_counter: dict[str, int] = {}
    manifest = []

    for src_path, ext in selected:
        idx = ext_counter.get(ext, 0) + 1
        ext_counter[ext] = idx

        # 复制固件并同步生成预期数据
        fixture_name = make_fixture_name(src_path, ext, idx)
        fixture_dst = fixtures_dir / fixture_name
        expected_dst = expected_dir / f"{fixture_dst.stem}.json"

        shutil.copy2(src_path, fixture_dst)

        if args.pre_fill:
            result = run_parser(fixture_dst, ext)
            result["_source_file"] = str(src_path)
            result["_verified"] = False
            result["_notes"] = (
                "pre-filled by parser. review and set _verified=true."
                if not result.get("_error")
                else f"parser error: {result['_error']}. fill in manually."
            )
            data = result
        else:
            data = build_skeleton(ext)
            data["_source_file"] = str(src_path)

        with open(expected_dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        has_error = bool(data.get("_error"))
        status = "ERR" if has_error else ("pre" if args.pre_fill else "skel")
        size_kb = src_path.stat().st_size / 1024
        n_items = len(data.get("items", []))
        print(f"  [{status}] {fixture_name} ({size_kb:.0f}KB, {n_items} items)")

        manifest.append({
            "fixture": fixture_name, "source": str(src_path),
            "size_kb": round(size_kb, 1), "ext": ext,
            "items_count": n_items, "has_error": has_error,
        })

    return manifest


def main():
    """CLI 入口：扫描 → 抽样 → 复制固件 → 生成预期文件。"""
    p = argparse.ArgumentParser(
        description="Generate Golden File test scaffolding")
    p.add_argument("--source", "-s", required=True, type=Path)
    p.add_argument("--target", "-t", type=Path, default=DEFAULT_TARGET)
    p.add_argument("--sample", "-n", type=int, default=DEFAULT_SAMPLE)
    p.add_argument("--ext", nargs="+")
    p.add_argument("--pre-fill", "-p", action="store_true")
    p.add_argument("--strategy", choices=["diverse", "random", "largest"],
                   default="diverse")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    random.seed(args.seed)

    # 校验源目录是否存在
    if not args.source.is_dir():
        print(f"source dir not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    allowed = SUPPORTED_EXT
    if args.ext:
        allowed = {f".{e.lstrip('.')}" for e in args.ext}

    print(f"scanning: {args.source}")
    grouped, skipped = discover_files(args.source, allowed)
    total = _print_scan_summary(grouped, skipped)

    if total == 0:
        print("no files found, exiting.")
        return

    selected = sample_files(grouped, args.sample, args.strategy)
    print(f"\nsampled ({args.strategy}, seed={args.seed}): {len(selected)}")

    # 预演模式：仅打印选择结果，不写入任何文件
    if args.dry_run:
        print("\n-- DRY RUN --")
        for i, (src, ext) in enumerate(selected, 1):
            print(f"  [{i:02d}] {ext} {src.stat().st_size / 1024:>8.1f} KB"
                  f"  {src}")
        print(f"\n{len(selected)} files. remove --dry-run to execute.")
        return

    # 在输出目标下构造测试夹具/和/目录
    fixtures_dir = args.target / "fixtures"
    expected_dir = args.target / "expected"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nwriting to {args.target}/")
    manifest = _generate_expected(selected, args, fixtures_dir, expected_dir)

    # 写入清单文件，支持回溯到源文件
    manifest_path = args.target / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    conftest_path = args.target / "conftest.py"
    # 如不存在则生成（绝不复写用户已有改动）
    if not conftest_path.exists():
        conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")
        print(f"\ngenerated {conftest_path}")

    print(f"\n{'=' * 50}")
    print(f"fixtures:  {fixtures_dir} ({len(selected)} files)")
    print(f"expected:  {expected_dir} ({len(selected)} json)")
    print(f"manifest:  {manifest_path}")
    if args.pre_fill:
        errors = sum(1 for m in manifest if m["has_error"])
        print(f"pre-fill:  {len(manifest) - errors} ok / {errors} errors")
    print("\nnext steps:")
    print("  1. review expected/*.json, set _verified=true")
    print(f"  2. pytest {args.target}/ -v")


CONFTEST_TEMPLATE = '''\
"""Golden File test infrastructure: auto-pair fixture <-> expected."""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXPECTED_DIR = Path(__file__).parent / "expected"


def discover_cases():
    """Return cases with a verified expected.json counterpart."""
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
    """Parametrized fixture: (stem, raw_bytes, ext, expected_dict, path)."""
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
'''

if __name__ == "__main__":
    main()
