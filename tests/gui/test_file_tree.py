# tests/gui/test_file_tree.py
import os
import sys
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def test_file_tree_has_top_level_items(window):
    """文件树应有顶级节点：桌面、文档、下载、此电脑。"""
    tree = window.file_tree
    assert tree.topLevelItemCount() >= 4

    labels = {tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())}
    assert "桌面" in labels
    assert "文档" in labels
    assert "下载" in labels
    assert "此电脑" in labels


def test_file_tree_left_width_is_200(window, qtbot):
    """左侧文件树区域宽度应固定为 200。"""
    splitter = window.centralWidget()
    sizes = splitter.sizes()
    assert sizes[0] == 200


def test_file_tree_expand_drives(window, qtbot):
    """展开「此电脑」应显示驱动器。"""
    # 找到"此电脑"节点
    tree = window.file_tree
    this_pc = None
    for i in range(tree.topLevelItemCount()):
        if tree.topLevelItem(i).text(0) == "此电脑":
            this_pc = tree.topLevelItem(i)
            break
    assert this_pc is not None

    # 展开
    tree.setCurrentItem(this_pc)
    this_pc.setExpanded(True)
    qtbot.wait(300)

    # 应有至少一个驱动器
    assert this_pc.childCount() >= 1
    drive_label = this_pc.child(0).text(0)
    assert len(drive_label) >= 2  # e.g. "C:" or "C:\"
