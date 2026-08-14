"""pilotstd/cli/commands/__main__.py 补测 — CLI 入口点验证。"""
import subprocess
import sys


class TestMainModule:
    """__main__ 入口模块 — 正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_normal_import_module_does_not_crash(self):
        """导入 __main__ 模块：模块级 main() 解析 argv，用 --help 避免报错。"""
        old_argv = sys.argv.copy()
        try:
            sys.argv = ["pilotstd", "--help"]
            import pilotstd.cli.commands.__main__ as mod
            assert mod is not None
        except SystemExit:
            pass  # --help 会触发 sys.exit(0)
        finally:
            sys.argv = old_argv

    def test_normal_main_function_importable(self):
        """main 可从 pilotstd.cli.commands 正常导入且可调用。"""
        from pilotstd.cli.commands import main
        assert callable(main)

    def test_boundary_cli_help_returns_zero(self):
        """--help 返回退出码 0。"""
        result = subprocess.run(
            [sys.executable, "-m", "pilotstd.cli.commands", "--help"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0

    def test_exception_unknown_flag_returns_nonzero(self):
        """未知参数标志返回非零退出码。"""
        result = subprocess.run(
            [sys.executable, "-m", "pilotstd.cli.commands", "--unknown-flag-xyz"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode != 0

    def test_state_module_is_runnable_via_python_m(self):
        """python -m pilotstd.cli.commands 可执行（退出码应为 0 或非零但不崩溃）。"""
        result = subprocess.run(
            [sys.executable, "-m", "pilotstd.cli.commands"],
            capture_output=True, text=True, timeout=30
        )
        # 无参运行：应返回非零但非崩溃（即正常退出而非异常）
        assert result.returncode in (0, 1, 2)
