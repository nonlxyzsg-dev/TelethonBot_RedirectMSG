"""Тесты модуля paths (портативность)."""

from __future__ import annotations

import sys
from pathlib import Path

from bot import paths


def test_app_dir_when_not_frozen():
    """В dev-режиме app_dir() возвращает корень репозитория."""
    assert not getattr(sys, "frozen", False)
    result = paths.app_dir()
    # __init__.py лежит в src/bot/, значит корень — на 2 уровня выше
    expected = Path(paths.__file__).resolve().parents[2]
    assert result == expected


def test_app_dir_when_frozen(monkeypatch, tmp_path):
    """Для frozen-режима app_dir() — папка рядом с sys.executable."""
    fake_exe = tmp_path / "TelethonBot.exe"
    fake_exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert paths.app_dir() == tmp_path


def test_path_for_names():
    assert paths.path_for(paths.ENV_FILE).name == ".env"
    assert paths.path_for(paths.CONFIG_JSON).name == "config.json"
    assert paths.path_for(paths.CONFIG_BAK).name == "config.json.bak"
    assert paths.path_for(paths.PROXIES_FILE).name == "proxies.txt"
    assert paths.path_for(paths.LOG_FILE).name == "telethon_log.log"


def test_resolve_combines_with_app_dir():
    result = paths.resolve("foo.txt")
    assert result == paths.app_dir() / "foo.txt"
