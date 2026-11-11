"""P2-14：fresh Docker 的 site_capabilities.yaml 必须自动播种且不覆盖用户配置。"""

from pathlib import Path


def test_dockerfile_ships_default_capabilities():
    text = Path("docker/Dockerfile").read_text(encoding="utf-8")
    assert "COPY config/site_capabilities.yaml /app/config-defaults/site_capabilities.yaml" in text


def test_entrypoint_seeds_only_when_missing():
    text = Path("docker/entrypoint.sh").read_text(encoding="utf-8")
    assert "[ ! -f /app/config/site_capabilities.yaml ]" in text
    assert "/app/config-defaults/site_capabilities.yaml" in text
    assert "cp /app/config-defaults/site_capabilities.yaml /app/config/site_capabilities.yaml" in text
