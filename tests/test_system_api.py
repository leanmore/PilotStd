# tests/test_system_api.py
# /api/system 接口测试（TestUpdateFunction 已拆分至 tests/test_update_function.py）

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if __name__ == "__main__":
    import unittest
    unittest.main()
