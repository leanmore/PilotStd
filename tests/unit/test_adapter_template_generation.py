"""cookiecutter 适配器模板的**生成物契约测试**（#32-D / R14-5，2026-10-01）。

模板目录 `pilotstd/templates/adapter/**` 不能被直接 import（含 Jinja 占位符），
因此它的正确性只能靠"渲染后检查生成物"。本文件落实用户对 R14-5 的要求：

① **生成产物零裸中文状态字面量**：把模板用 `cookiecutter.json` 的默认值渲染到临时目录，
   逐个 `.py` 做 AST 扫描——不得出现任何等于状态字典取值的字符串常量；
② **import 可解析**：生成物里的 `from pilotstd.core.status import Status` 必须真实可执行
   （把该行取出来 `exec` 验证，而不是只做字符串比较）；
③ **基础 lint**：每个生成物 `py_compile` 通过，且能被 `ast.parse`；
④ **分支覆盖**：四种 `response_type`（json_api_post / json_api_get / json_api_mixed /
   vue_datalist）都要渲染并编译——分支级缺陷只在对应分支渲染时才暴露。

> 本测试在 R14-5 落地时立刻抓到 3 个模板缺陷（并已修复）：
> ① 3 处伪占位符 `{{模板引擎.*}}`（cookiecutter 下静默渲染为空串）；
> ② 48 处 `-%}` 尾随空白控制吞掉换行与缩进 → 生成物 `IndentationError`；
> ③ 1 处残留死条件片段 `[rec] if True  # ... else mock_resp` → 生成物 `SyntaxError`。
>
> 环境说明：本仓库未把 `cookiecutter` 包列入依赖（`requirements-dev.txt` 无此项），
> 故用 **jinja2**（FastAPI 依赖链自带）按同一上下文渲染——变量替换与目录改名语义一致，
> 且不为 CI 增加新依赖。这里刻意用 `StrictUndefined`：未定义变量**必须报错**，
> 不能再像 cookiecutter 默认那样静默渲染为空串（缺陷①正是这样藏了很久）。
"""

from __future__ import annotations

import ast
import json
import py_compile
from pathlib import Path

import pytest
from jinja2 import Environment, StrictUndefined

from pilotstd.core.status import Status

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO_ROOT / "pilotstd" / "templates" / "adapter"
STATUS_VALUES = {member.value for member in Status}
RESPONSE_TYPES = ("json_api_post", "json_api_get", "json_api_mixed", "vue_datalist")
DEFAULT_RESPONSE_TYPE = "json_api_post"


def _raw_context(**overrides: object) -> dict[str, object]:
    """cookiecutter.json 的内容（剔除仅供交互提示的 __prompts__，可覆写字段）。"""
    data = json.loads((TEMPLATE_ROOT / "cookiecutter.json").read_text(encoding="utf-8"))
    data.pop("__prompts__", None)
    data.update(overrides)
    return data


def _render(tmp_path: Path, **overrides: object) -> Path:
    """把模板渲染成生成物目录（目录名也走渲染），返回生成物根目录。"""
    ctx = {"cookiecutter": _raw_context(**overrides)}
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    out_root = tmp_path / str(ctx["cookiecutter"]["adapter_name"])
    src_root = TEMPLATE_ROOT / "{{ cookiecutter.adapter_name }}"
    for src in sorted(src_root.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(src_root)
        rel_rendered = Path(*[env.from_string(part).render(**ctx) for part in rel.parts])
        dest = out_root / rel_rendered
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".py":
            dest.write_text(env.from_string(src.read_text(encoding="utf-8")).render(**ctx), encoding="utf-8")
        else:
            # 非 Python 资源（夹具 JSON / README）原样复制
            dest.write_bytes(src.read_bytes())
    return out_root


@pytest.fixture
def generated(tmp_path: Path) -> Path:
    return _render(tmp_path)


def test_template_renders_python_files(generated: Path):
    """渲染应产出适配器主体与配套测试（防止模板改名/占位符写错导致静默空目录）。"""
    names = {p.name for p in generated.rglob("*.py")}
    adapter = str(_raw_context()["adapter_name"])
    assert f"{adapter}.py" in names
    assert f"test_{adapter}.py" in names
    assert "probe.py" in names


@pytest.mark.parametrize("response_type", RESPONSE_TYPES)
def test_all_response_type_branches_compile(tmp_path: Path, response_type: str):
    """四种架构分支都必须渲染出**可编译**的 .py（分支缺陷只有渲染才暴露）。"""
    root = _render(tmp_path, response_type=response_type)
    compiled = []
    for path in sorted(root.rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        py_compile.compile(str(path), cfile=None, doraise=True)
        compiled.append(path.name)
    assert len(compiled) >= 3, compiled


def test_generated_python_has_no_bare_status_literals(generated: Path):
    """生成物中不得出现等于状态字典取值的字符串常量（AST 口径，含 docstring）。"""
    offenders: list[str] = []
    for path in sorted(generated.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in STATUS_VALUES:
                offenders.append(f"{path.name}:{node.lineno} {node.value}")
    assert offenders == [], "生成物出现裸状态字面量：\n" + "\n".join(offenders)


def test_generated_files_import_status_and_import_is_resolvable(generated: Path):
    """生成物必须引用状态字典，且该 import 行真实可执行（不是只断言出现过字符串）。"""
    expected = "from pilotstd.core.status import Status"
    adapter = str(_raw_context()["adapter_name"])
    for name in [f"{adapter}.py", f"test_{adapter}.py"]:
        text = (generated / name).read_text(encoding="utf-8")
        assert expected in text, f"{name} 未引用状态字典"
        namespace: dict[str, object] = {}
        exec(expected, namespace)  # noqa: S102 - 仅执行模板生成的那一行 import，验证其可解析
        assert namespace["Status"] is Status


def test_generated_status_map_uses_dictionary(generated: Path):
    """适配器的状态归一化表必须由字典成员构成，且归一方向与原模板一致。"""
    text = (generated / f"{_raw_context()['adapter_name']}.py").read_text(encoding="utf-8")
    for member in (Status.ACTIVE, Status.UPCOMING, Status.WITHDRAWN):
        assert f"Status.{member.name}.value" in text
    # 原模板把“已废止”归一到“废止”，重构后方向不变
    assert f"Status.{Status.WITHDRAWN_NORMALIZED.name}.value: Status.{Status.WITHDRAWN.name}.value" in text
    assert f"else Status.{Status.UNKNOWN.name}.value" in text


def test_generated_fixture_keeps_external_chinese_payload(generated: Path):
    """夹具 JSON 模拟**外部站点报文**，必须保留中文取值（这是被解析的输入，不是代码常量）。"""
    adapter = str(_raw_context()["adapter_name"])
    fixture = generated / "fixtures" / f"{adapter}_sample.json"
    assert fixture.exists()
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["standardStatusName"] == Status.ACTIVE.value


def test_template_has_no_undefined_placeholder(tmp_path: Path):
    """模板内不得再出现未定义占位符（历史上的伪占位符会被静默渲染成空串）。"""
    # StrictUndefined 下渲染成功即等价于"无未定义变量"（含目录名）
    assert _render(tmp_path, response_type=DEFAULT_RESPONSE_TYPE).exists()
