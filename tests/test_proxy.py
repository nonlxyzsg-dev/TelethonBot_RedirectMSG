"""Тесты парсера и загрузчика MTProxy."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.proxy import MTProxy, load_proxies, parse_mtproxy_uri


class TestParseMTProxyURI:
    def test_valid_uri(self):
        uri = "tg://proxy?server=194.87.57.180&port=443&secret=ddb7c4685b50c48b91a64412b63408dc2c"
        proxy = parse_mtproxy_uri(uri)
        assert proxy.host == "194.87.57.180"
        assert proxy.port == 443
        assert proxy.secret == "ddb7c4685b50c48b91a64412b63408dc2c"

    def test_long_secret_with_fake_tls(self):
        long_secret = "eeb7c4685b50c48b91a64412b63408dc2c7777772e676f6f676c652e636f6d"
        uri = f"tg://proxy?server=194.87.57.180&port=443&secret={long_secret}"
        proxy = parse_mtproxy_uri(uri)
        assert proxy.secret == long_secret

    def test_as_tuple(self):
        proxy = MTProxy(host="h", port=1, secret="dd")
        assert proxy.as_tuple() == ("h", 1, "dd")

    def test_masked_does_not_leak_secret(self):
        proxy = MTProxy(host="h", port=1, secret="ddb7c4685b50c48b91a64412b63408dc2c")
        assert proxy.secret not in proxy.masked()

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Пустая"):
            parse_mtproxy_uri("")

    def test_wrong_scheme(self):
        with pytest.raises(ValueError, match="tg://proxy"):
            parse_mtproxy_uri("http://1.2.3.4:443?secret=dd")

    def test_missing_secret(self):
        with pytest.raises(ValueError, match="secret"):
            parse_mtproxy_uri("tg://proxy?server=1.1.1.1&port=443")

    def test_non_numeric_port(self):
        with pytest.raises(ValueError, match="port"):
            parse_mtproxy_uri("tg://proxy?server=1.1.1.1&port=abc&secret=dd")

    def test_port_out_of_range(self):
        with pytest.raises(ValueError, match="Некорректный порт"):
            parse_mtproxy_uri("tg://proxy?server=1.1.1.1&port=99999&secret=dd")

    def test_non_hex_secret(self):
        with pytest.raises(ValueError, match="hex"):
            parse_mtproxy_uri("tg://proxy?server=1.1.1.1&port=443&secret=ZZZ")


class TestLoadProxies:
    def test_missing_file(self, tmp_path):
        assert load_proxies(tmp_path / "nope.txt") == []

    def test_comments_and_blanks_ignored(self, tmp_path):
        path = tmp_path / "p.txt"
        path.write_text(
            "# комментарий\n"
            "\n"
            "tg://proxy?server=1.1.1.1&port=443&secret=ddb7c4685b50c48b91a64412b63408dc2c\n"
            "\n"
            "# tg://proxy?server=2.2.2.2&port=443&secret=dd\n",
            encoding="utf-8",
        )
        proxies = load_proxies(path)
        assert len(proxies) == 1
        assert proxies[0].host == "1.1.1.1"

    def test_invalid_line_skipped_but_others_loaded(self, tmp_path):
        path = tmp_path / "p.txt"
        path.write_text(
            "bad line here\n"
            "tg://proxy?server=1.1.1.1&port=443&secret=ddb7c4685b50c48b91a64412b63408dc2c\n",
            encoding="utf-8",
        )
        proxies = load_proxies(path)
        assert len(proxies) == 1

    def test_all_four_shipped_examples(self):
        """Все 4 боевых прокси из proxies.txt парсятся без ошибок."""
        path = Path(__file__).resolve().parents[1] / "proxies.txt"
        proxies = load_proxies(path)
        assert len(proxies) == 4
        for p in proxies:
            assert p.host == "194.87.57.180"
            assert p.port in (443, 8443)
