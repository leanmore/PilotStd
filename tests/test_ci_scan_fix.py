import faulthandler
import sys

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QProgressBar, QPushButton, QVBoxLayout, QWidget

faulthandler.enable()


class MockScanWorker(QThread):
    """模拟极限高负载的 Worker 线程"""

    progress = pyqtSignal(int, int)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal()

    def __init__(self, total_files=100000):
        super().__init__()
        self.total_files = total_files

    def run(self):
        for i in range(1, self.total_files + 1):
            # 核心修复点 1：Worker 端固定频率节流
            if i % 50 == 0 or i == self.total_files:
                self.progress.emit(i, self.total_files)

            # 模拟高频批次数据发射
            if i % 20 == 0:
                batch = [(j, f"MockData_{j}") for j in range(i - 19, i + 1)]
                self.batch_ready.emit(batch)

        self.finished_signal.emit()


class TestMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CI Automated Test")
        self.resize(400, 200)

        layout = QVBoxLayout()
        self.status_label = QLabel("Waiting for test...")
        self.progress_bar = QProgressBar()
        self.start_btn = QPushButton("Start Test")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.start_btn)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # 平滑动画变量
        self._target_progress = 0
        self._current_progress = 0.0
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._animate_progress)

        self.start_btn.clicked.connect(self.start_stress_test)

        # 用于自动化断言的计数器
        self.batch_update_count = 0

    def start_stress_test(self):
        self.start_btn.setEnabled(False)
        self.status_label.setText("Running 100k files stress test...")
        self.progress_bar.setValue(0)

        self.worker = MockScanWorker(total_files=100000)

        # 核心修复点 2：显式声明 QueuedConnection
        self.worker.progress.connect(self._on_raw_progress, Qt.ConnectionType.QueuedConnection)
        self.worker.batch_ready.connect(self._on_batch_ready, Qt.ConnectionType.QueuedConnection)
        self.worker.finished_signal.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)

        self.worker.start()

    def _on_raw_progress(self, cur: int, total: int):
        self._target_progress = int(cur / total * 100) if total else 0
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def _animate_progress(self):
        # 核心修复点 3：主线程平滑插值动画
        diff = self._target_progress - self._current_progress
        if abs(diff) < 0.5:
            self._current_progress = self._target_progress
            self.progress_bar.setValue(int(self._current_progress))
            self._progress_timer.stop()
        else:
            self._current_progress += diff * 0.2
            self.progress_bar.setValue(int(self._current_progress))

    def _on_batch_ready(self, batch_rows: list):
        # 核心修复点 4：批量 UI 更新
        self.batch_update_count += 1
        _ = [row[0] for row in batch_rows]  # 模拟轻量数据处理，不阻塞主线程

    def _on_finished(self):
        self.status_label.setText("Test Completed Successfully!")
        self.start_btn.setEnabled(True)


def run_automated_test():
    """
    CI 自动化测试入口：
    1. 启动应用并触发测试
    2. 验证程序是否存活（未崩溃）
    3. 验证 UI 是否响应
    4. 验证批量更新逻辑是否生效
    """
    app = QApplication(sys.argv)
    window = TestMainWindow()
    window.show()

    # 模拟用户点击按钮
    QTimer.singleShot(100, window.start_stress_test)

    # 在测试运行 3 秒后，执行自动化断言
    def assert_results():
        print("\n[CI TEST REPORT]")

        # 断言 1：程序存活且 UI 响应
        is_window_active = window.isActiveWindow() or window.isVisible()
        print(f"[{'PASS' if is_window_active else 'FAIL'}] 程序存活且 UI 可见 (未发生 c0000409 崩溃)")

        # 断言 2：进度条已达到 100%
        progress_reached = window.progress_bar.value() >= 99
        print(f"[{'PASS' if progress_reached else 'FAIL'}] 进度条已完成 (当前值: {window.progress_bar.value()}%)")

        # 断言 3：批量更新逻辑被正确触发
        batch_processed = window.batch_update_count > 0
        status3 = "PASS" if batch_processed else "FAIL"
        print(f"[{status3}] 批量 UI 更新逻辑已生效 (批次: {window.batch_update_count})")

        # 断言 4：平滑动画定时器已停止（说明任务已完全结束）
        timer_stopped = not window._progress_timer.isActive()
        print(f"[{'PASS' if timer_stopped else 'FAIL'}] 平滑动画定时器已正常停止")

        # 汇总结果
        all_passed = all([is_window_active, progress_reached, batch_processed, timer_stopped])
        final_status = "ALL TESTS PASSED" if all_passed else "TESTS FAILED"
        print(f"\n[FINAL RESULT] {final_status}\n")

        app.quit()
        sys.exit(0 if all_passed else 1)

    # 设定 5 秒后执行断言
    QTimer.singleShot(5000, assert_results)

    sys.exit(app.exec())


if __name__ == "__main__":
    run_automated_test()
