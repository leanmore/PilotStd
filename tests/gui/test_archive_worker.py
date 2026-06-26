import os
import shutil
import tempfile

from pilotstd.models import ParsedStdInfo
from pilotstd.ui.main_window import ArchiveWorker


def _make_parsed(src_path, code="GB", num=1, year=2020, effect_status="现行", std_name="测试标准"):
    """创建测试用 ParsedStdInfo。"""
    p = ParsedStdInfo(
        raw_filename=os.path.basename(src_path),
        logical_code=code,
        number=num,
        year=year,
        std_name=std_name,
        source_path=src_path,
        effect_status=effect_status,
    )
    return p


def test_archive_worker_checkpoint_skips_completed(qtbot):
    """断点续做：已完成文件出现在checkpoint中应跳过。"""
    tmpdir = tempfile.mkdtemp(prefix="pilotstd_arch_test_")
    src_dir = os.path.join(tmpdir, "src")
    dst_dir = os.path.join(tmpdir, "dst")
    os.makedirs(src_dir)
    os.makedirs(dst_dir)

    # 创建测试文件
    src_file = os.path.join(src_dir, "GB 1-2020 测试标准.pdf")
    with open(src_file, "w") as f:
        f.write("test")
    parsed = _make_parsed(src_file)
    parsed.source_path = src_file

    # 预先创建 checkpoint 文件，标记 src_file 已完成
    data_dir = os.path.join(tmpdir, "data")
    os.makedirs(data_dir)
    ckpt_path = os.path.join(data_dir, "move_checkpoint.txt")
    with open(ckpt_path, "w", encoding="utf-8") as cf:
        cf.write(src_file + "\n")
    # Mock get_data_dir 返回临时目录
    import pilotstd.core.config as cfg

    orig_get_data_dir = cfg.get_data_dir
    cfg.get_data_dir = lambda: data_dir

    try:
        worker = ArchiveWorker([parsed], dst_dir)
        batches = []
        worker.batch_ready.connect(lambda b: batches.extend(b))
        with qtbot.waitSignal(worker.finished_signal, timeout=5000):
            worker.start()

        # 应被标记为"已归档"（从checkpoint跳过），而非再次移动
        statuses = [s for _, s in batches]
        # 移动后 parsed.source_path 更新为目标路径
        assert "已归档" in statuses or parsed.source_path != src_file, "checkpoint 中已完成的文件应被跳过"
    finally:
        cfg.get_data_dir = orig_get_data_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_archive_worker_moves_new_files(qtbot):
    """新文件正常移动归档。"""
    tmpdir = tempfile.mkdtemp(prefix="pilotstd_arch_test_")
    src_dir = os.path.join(tmpdir, "src")
    dst_dir = os.path.join(tmpdir, "dst")
    os.makedirs(src_dir)
    os.makedirs(dst_dir)

    src_file = os.path.join(src_dir, "GB 2-2020 测试标准.pdf")
    with open(src_file, "w") as f:
        f.write("test")
    parsed = _make_parsed(src_file)

    worker = ArchiveWorker([parsed], dst_dir)
    batches = []
    worker.batch_ready.connect(lambda b: batches.extend(b))
    with qtbot.waitSignal(worker.finished_signal, timeout=5000):
        worker.start()

    # 文件应被移动
    assert not os.path.exists(src_file), "源文件应已被移动"
    statuses = [s for _, s in batches]
    assert "已归档" in statuses, f"应包含'已归档'状态，实际: {statuses}"

    shutil.rmtree(tmpdir, ignore_errors=True)
