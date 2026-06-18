# pytest 收集时忽略独立运行脚本（含模块级 sys.exit / parse_args 会导致收集失败）
collect_ignore = [
    "stress_selfcheck.py",
    "stress_web.py",
    "gui",
    "stress_driver.py",
    "stress_winui.py",  # 由 stress_driver.py 显式调用，不走自动收集
]


def pytest_addoption(parser):
    """stress_winui.py 所需的自定义参数，由 stress_driver.py 传入。"""
    parser.addoption("--source", help="源目录路径")
    parser.addoption("--output", help="输出目录路径")
    parser.addoption("--step1", help="step1.json 路径")
    parser.addoption("--step2", help="step2.json 输出路径")
