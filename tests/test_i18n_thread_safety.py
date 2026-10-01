"""i18n 执行上下文安全测试（专项：`_lang` 线程串扰修复）。

原实现把"当前语言"存在模块级全局 `_lang` / `_current`，任何线程调用
`set_language()` 都会改写**所有**线程看到的语言。通知构建器、渲染器、聚合器
都在 `ThreadPoolExecutor` 与 `asyncio` 任务中被调用，会读到错误语言。
修复后语言存于 `contextvars.ContextVar`，本文件锁定该不变量。
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from pilotstd.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language,
    language,
    set_language,
    t,
)

# 用一个三语互不相同的键做断言（`notification.renderer.empty`）
PROBE_KEY = "notification.renderer.empty"


def _restore_language():
    """用例结束后恢复语言（与 conftest 的 i18n 隔离同源）。"""
    before = get_language()

    def _restore():
        set_language(before)

    return _restore


@pytest.fixture(autouse=True)
def _isolate_language():
    """每个用例前后都归位到默认语言，避免用例间通过 ContextVar 泄漏状态。"""
    set_language(DEFAULT_LANGUAGE)
    yield
    set_language(DEFAULT_LANGUAGE)


class TestThreadIsolation:
    """多线程竞争：各线程 set_language 后必须各自看到自己的语言。"""

    def test_concurrent_threads_do_not_crosstalk(self):
        """N 线程各设不同语言并并发读 t()，各自结果必须匹配自己设的语言。

        用 Barrier 让所有线程**同时**起跑，最大化 set/read 的交错概率——
        原全局实现下该用例必红（后写者会覆盖先写者的语言）。
        """
        languages = ["zh_CN", "zh_TW", "en"]
        rounds = 6
        # 预先取各语言期望值（在主线程取，避免把被测代码引入期望值计算）
        expected: dict[str, str] = {}
        for lang in languages:
            set_language(lang)
            expected[lang] = t(PROBE_KEY)
        # 期望值必须互不相同，否则用例没有判别力
        assert len(set(expected.values())) == len(languages)

        errors: list[str] = []
        barrier = threading.Barrier(len(languages) * rounds)

        def worker(lang: str) -> None:
            barrier.wait()  # 对齐起跑点
            set_language(lang)
            for _ in range(50):
                got = t(PROBE_KEY)
                if got != expected[lang]:
                    errors.append(f"{lang}: 期望 {expected[lang]!r} 实得 {got!r}")
                    return
                if get_language() != lang:
                    errors.append(f"{lang}: get_language() 漂移为 {get_language()!r}")
                    return

        threads = [
            threading.Thread(target=worker, args=(lang,))
            for _ in range(rounds)
            for lang in languages
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert errors == [], f"检测到线程串扰 {len(errors)} 例：{errors[:3]}"

    def test_thread_pool_workers_are_isolated(self):
        """线程池复用工作线程时，各任务的语言必须自洽。"""

        def task(lang: str) -> tuple[str, str]:
            set_language(lang)
            return get_language(), t(PROBE_KEY)

        set_language("en")
        expected_en = t(PROBE_KEY)
        set_language("zh_TW")
        expected_tw = t(PROBE_KEY)
        assert expected_en != expected_tw
        set_language(DEFAULT_LANGUAGE)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(task, ["en", "zh_TW"] * 8))

        for lang, rendered in results:
            want = expected_en if lang == "en" else expected_tw
            assert rendered == want, f"{lang}: 文案 {rendered!r} 与语言 {lang!r} 不匹配"

    def test_child_thread_is_immune_to_other_threads_language_writes(self):
        """子线程的语言**不受其它线程 set_language 影响**（本专项的核心不变量）。

        实测语义：新线程从**空上下文**开始，故 ContextVar 取其默认值 `zh_CN`
        （不继承父线程——继承只发生在 `asyncio.create_task`，见 TestAsyncIsolation）。
        关键在于：另一个线程持续把语言改成 `zh_TW` 时，本线程读到的必须仍是默认语言。

        这正是能确定性区分两种实现的不变量——旧模块级全局实现下，writer 线程的写入
        会立刻污染 reader（对照实验实测 6/6 被污染为 zh_TW）。
        """
        set_language("en")  # 父线程设为 en，用于证明"既不继承父值、也不受 writer 影响"
        default_rendered = None
        set_language(DEFAULT_LANGUAGE)
        default_rendered = t(PROBE_KEY)
        set_language("en")

        results: list[tuple[str, str]] = []
        writer_stop = threading.Event()

        def writer() -> None:
            # 持续把**自己上下文**的语言改成 zh_TW（旧实现下这会污染全局）
            while not writer_stop.is_set():
                set_language("zh_TW")

        def reader() -> None:
            # 本线程从不 set_language：读到的必须是 ContextVar 默认值
            results.append((get_language(), t(PROBE_KEY)))

        w = threading.Thread(target=writer, daemon=True)
        w.start()
        readers = [threading.Thread(target=reader) for _ in range(6)]
        for r in readers:
            r.start()
        for r in readers:
            r.join()
        writer_stop.set()
        w.join()

        assert results, "读取线程未产生结果"
        for lang, rendered in results:
            assert lang == DEFAULT_LANGUAGE, f"子线程语言被污染为 {lang!r}（期望 {DEFAULT_LANGUAGE}）"
            assert rendered == default_rendered, (
                f"子线程文案被污染：{rendered!r}（期望 {default_rendered!r}）"
            )

    def test_new_thread_starts_from_default_language(self):
        """新线程不继承其它线程设过的语言，从默认语言开始（有意行为变更）。

        原全局语义下子线程会"跟随"最后设置者，那是竞态而非特性；
        需要该效果的调用方应在自己的上下文内显式 `set_language()`。
        """
        set_language("en")
        assert get_language() == "en"

        seen: list[str] = []

        def worker() -> None:
            seen.append(get_language())

        th = threading.Thread(target=worker)
        th.start()
        th.join()

        assert seen == [DEFAULT_LANGUAGE]
        assert get_language() == "en"  # 主线程未受影响

    def test_concurrent_set_does_not_break_translation(self):
        """并发 set + 读下，t() 结果必须始终是**某个受支持语言**的合法文案。

        比逐个断言更弱，但能捕获"读到空表导致全量返回键名"这类崩坏。
        """
        valid = set()
        for lang in SUPPORTED_LANGUAGES:
            set_language(lang)
            valid.add(t(PROBE_KEY))
        set_language(DEFAULT_LANGUAGE)

        bad: list[str] = []
        stop = threading.Event()

        def writer(lang: str) -> None:
            while not stop.is_set():
                set_language(lang)

        def reader() -> None:
            for _ in range(200):
                got = t(PROBE_KEY)
                if got not in valid:
                    bad.append(got)
                    return

        writers = [
            threading.Thread(target=writer, args=(lang,), daemon=True) for lang in SUPPORTED_LANGUAGES
        ]
        readers = [threading.Thread(target=reader) for _ in range(4)]
        for w in writers:
            w.start()
        for r in readers:
            r.start()
        for r in readers:
            r.join()
        stop.set()
        for w in writers:
            w.join()

        assert bad == [], f"读到非法文案：{bad[:3]}"


class TestNestedSwitch:
    """同一线程内嵌套切换：退出后必须恢复外层语言。"""

    def test_nested_language_contexts_restore(self):
        set_language("zh_CN")
        with language("en"):
            assert get_language() == "en"
            with language("zh_TW"):
                assert get_language() == "zh_TW"
            assert get_language() == "en"  # 恢复外层
        assert get_language() == "zh_CN"  # 恢复最初

    def test_context_manager_restores_on_exception(self):
        set_language("zh_CN")
        with pytest.raises(RuntimeError):
            with language("en"):
                assert get_language() == "en"
                raise RuntimeError("boom")
        assert get_language() == "zh_CN"

    def test_deep_nesting(self):
        set_language("zh_CN")
        with language("en"):
            with language("zh_TW"):
                with language("en"):
                    assert get_language() == "en"
                assert get_language() == "zh_TW"
            assert get_language() == "en"
        assert get_language() == "zh_CN"

    def test_nested_switch_does_not_affect_other_threads(self):
        """嵌套切换期间，其它线程不得观察到内层语言。"""
        set_language("zh_CN")
        observed: list[str] = []
        inside = threading.Event()
        done = threading.Event()

        def worker() -> None:
            inside.wait(timeout=2)
            observed.append(get_language())
            done.set()

        th = threading.Thread(target=worker)
        th.start()
        with language("en"):
            inside.set()
            assert done.wait(timeout=2)
        th.join()
        assert observed == [DEFAULT_LANGUAGE]


class TestAsyncIsolation:
    """asyncio 任务间语言隔离（ContextVar 相对 threading.local 的关键优势）。"""

    def test_tasks_do_not_share_language(self):
        async def scenario() -> dict[str, str]:
            results: dict[str, str] = {}
            barrier = asyncio.Event()

            async def task(lang: str) -> None:
                set_language(lang)
                await barrier.wait()  # 三个任务都设完语言后再一起读
                await asyncio.sleep(0)
                results[lang] = get_language()

            tasks = [asyncio.create_task(task(lang)) for lang in SUPPORTED_LANGUAGES]
            await asyncio.sleep(0)  # 让各任务跑到 barrier.wait()
            barrier.set()
            await asyncio.gather(*tasks)
            return results

        results = asyncio.run(scenario())
        assert results == {lang: lang for lang in SUPPORTED_LANGUAGES}

    def test_task_creation_snapshots_current_language(self):
        """新建任务继承**创建时**的上下文（asyncio/ContextVar 语义）。

        这保证"在 en 上下文里派生的子任务按 en 渲染"，而不是读到主线程后续的改动。
        """

        async def scenario() -> tuple[str, str]:
            set_language("en")
            created_under_en = asyncio.create_task(_read_language())
            set_language("zh_TW")  # 创建之后再改
            return await created_under_en, get_language()

        async def _read_language() -> str:
            await asyncio.sleep(0)
            return get_language()

        task_value, after = asyncio.run(scenario())
        assert task_value == "en"      # 继承创建时语言
        assert after == "zh_TW"        # 调用方自身仍是后来设的值

    def test_language_context_in_async_task(self):
        async def scenario() -> tuple[str, str]:
            set_language("zh_CN")

            async def inner() -> str:
                with language("en"):
                    return get_language()

            inside = await inner()
            return inside, get_language()

        inside, outside = asyncio.run(scenario())
        assert inside == "en"
        assert outside == "zh_CN"


class TestFallback:
    """兜底行为必须确定：永不返回 None。"""

    def test_unsupported_language_falls_back_to_default(self):
        set_language("fr_FR")
        assert get_language() == DEFAULT_LANGUAGE
        # 回退后仍能取到真实文案（而非键名）
        assert t(PROBE_KEY) != PROBE_KEY

    def test_get_language_never_returns_none(self):
        set_language("")
        assert get_language() == DEFAULT_LANGUAGE

    def test_language_context_rejects_unsupported(self):
        set_language("zh_CN")
        with language("ja"):
            assert get_language() == DEFAULT_LANGUAGE
        assert get_language() == "zh_CN"

    def test_missing_key_still_fails_loud(self):
        """缺键仍回退键名（fail-loud 语义未被本次修复改变）。"""
        set_language("en")
        assert t("notification.__no_such_key__") == "notification.__no_such_key__"

    def test_all_supported_languages_resolve(self):
        """三语都必须能解析出互不相同的文案（防止回退逻辑误伤正常语言）。"""
        rendered = {}
        for lang in SUPPORTED_LANGUAGES:
            set_language(lang)
            rendered[lang] = t(PROBE_KEY)
            assert rendered[lang] != PROBE_KEY, f"{lang} 未取到文案"
        assert len(set(rendered.values())) == len(SUPPORTED_LANGUAGES)
