# tests/test_system_api.py
# /api/system/update 接口测试 — mock docker 命令，覆盖 10 个场景

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

# —— 直接测函数，绕过 HTTP 鉴权层 ——
from docker.api.system import update_container


class TestUpdateFunction(unittest.TestCase):
    def setUp(self):
        self.patch_cid = patch("docker.api.system._get_container_id")
        self.mock_cid = self.patch_cid.start()
        self.mock_cid.return_value = "abc123def456"

        self.patch_docker = patch("docker.api.system._run_docker")
        self.mock_docker = self.patch_docker.start()

        self.patch_exists = patch("os.path.exists", return_value=True)
        self.patch_exists.start()

    def tearDown(self):
        self.patch_cid.stop()
        self.patch_docker.stop()
        self.patch_exists.stop()

    def _set_docker_sequence(self, *outputs):
        results = []
        for out, rc in outputs:
            r = MagicMock()
            r.stdout = out
            r.returncode = rc
            results.append(r)
        self.mock_docker.side_effect = results

    # ── 10 场景 ──────────────────────────────────

    def test_01_new_image_compose_available(self):
        with patch.dict("os.environ", {"COMPOSE_FILE": "/app/c.yml", "COMPOSE_PROJECT_NAME": "p"}):
            self._set_docker_sequence(
                ('[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]', 0),
                ("sha256:old", 0),
                ("Downloaded newer image\n", 0),
                ("sha256:new", 0),
                ("done", 0),
            )
            import asyncio

            result = asyncio.run(update_container())
        self.assertTrue(result["updated"])
        self.assertTrue(result["restarted"])

    def test_02_already_latest(self):
        self._set_docker_sequence(
            ('[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]', 0),
            ("sha256:same", 0),
            ("Image is up to date\n", 0),
            ("sha256:same", 0),
        )
        import asyncio

        result = asyncio.run(update_container())
        self.assertFalse(result["updated"])

    def test_03_no_container_id(self):
        self.mock_cid.return_value = ""
        import asyncio

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_container())
        self.assertEqual(ctx.exception.status_code, 500)

    def test_04_docker_inspect_fails(self):
        call_count = [0]

        def _fail(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("docker.sock 未挂载")
            r = MagicMock()
            r.stdout = '[{"Image": "test"}]'
            r.returncode = 0
            return r

        self.mock_docker.side_effect = _fail
        import asyncio

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_container())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_05_docker_pull_network_error(self):
        call_count = [0]

        def _fail(*args, **kwargs):
            call_count[0] += 1
            if "pull" in args[0]:
                raise RuntimeError("network error")
            r = MagicMock()
            r.returncode = 0
            r.stdout = '[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]' if call_count[0] == 1 else "sha256:ok"
            return r

        self.mock_docker.side_effect = _fail
        import asyncio

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_container())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_06_no_compose_file(self):
        with patch.dict("os.environ", {}, clear=True):
            self._set_docker_sequence(
                ('[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]', 0),
                ("sha256:old", 0),
                ("Downloaded newer image\n", 0),
                ("sha256:new", 0),
            )
            import asyncio

            result = asyncio.run(update_container())
        self.assertTrue(result["updated"])
        self.assertFalse(result["restarted"])

    def test_07_compose_up_fails(self):
        call_count = [0]

        def _fail(*args, **kwargs):
            call_count[0] += 1
            if "compose" in args[0]:
                raise RuntimeError("compose up failed")
            r = MagicMock()
            r.returncode = 0
            if call_count[0] == 1:
                r.stdout = '[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]'
            elif call_count[0] == 2:
                r.stdout = "sha256:old"
            elif call_count[0] == 3:
                r.stdout = "Downloaded newer image\n"
            else:
                r.stdout = "sha256:new"
            return r

        self.mock_docker.side_effect = _fail
        with patch.dict("os.environ", {"COMPOSE_FILE": "/app/c.yml", "COMPOSE_PROJECT_NAME": "p"}):
            import asyncio

            result = asyncio.run(update_container())
        self.assertTrue(result["updated"])
        self.assertFalse(result["restarted"])

    def test_08_docker_pull_timeout(self):
        import subprocess

        self.mock_docker.side_effect = subprocess.TimeoutExpired("pull", 300)
        import asyncio

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_container())
        self.assertEqual(ctx.exception.status_code, 504)

    def test_09_old_digest_empty(self):
        call_count = [0]

        def _no_old(*args, **kwargs):
            call_count[0] += 1
            r = MagicMock()
            r.returncode = 0
            if call_count[0] == 1:
                r.stdout = '[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]'
            elif "RepoDigests" in str(args):
                r.stdout = ""
            else:
                r.stdout = "sha256:new"
            return r

        self.mock_docker.side_effect = _no_old
        with patch.dict("os.environ", {"COMPOSE_FILE": "/app/c.yml", "COMPOSE_PROJECT_NAME": "p"}):
            import asyncio

            result = asyncio.run(update_container())
        self.assertTrue(result["updated"])

    def test_10_no_layers_but_digest_differs(self):
        with patch.dict("os.environ", {"COMPOSE_FILE": "/app/c.yml", "COMPOSE_PROJECT_NAME": "p"}):
            self._set_docker_sequence(
                ('[{"Image": "ghcr.io/leanmore/pilotstd:latest"}]', 0),
                ("sha256:old", 0),
                ("Already exists\n", 0),
                ("sha256:new", 0),
                ("done", 0),
            )
            import asyncio

            result = asyncio.run(update_container())
        self.assertTrue(result["updated"])
        self.assertEqual(result["old_digest"], "sha256:old")
        self.assertEqual(result["new_digest"], "sha256:new")


if __name__ == "__main__":
    unittest.main()
