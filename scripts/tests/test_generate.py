"""Tests for generate.py — orchestration, file I/O, and end-to-end pipeline."""

import ipaddress
import json
import time
from unittest.mock import MagicMock, patch

from generate import (
    load_overrides,
    process_country,
    read_file_hash,
    write_if_changed,
    write_text_if_changed,
)

N = ipaddress.ip_network


# ---------------------------------------------------------------------------
# read_file_hash
# ---------------------------------------------------------------------------


class TestReadFileHash:
    def test_reads_hash_from_header(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("# Country: Test\n# Hash: sha256:abc123def\n10.0.0.0/8\n")
        assert read_file_hash(f) == "abc123def"

    def test_missing_file(self, tmp_path):
        assert read_file_hash(tmp_path / "nope.txt") is None

    def test_no_hash_line(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("# Country: Test\n10.0.0.0/8\n")
        assert read_file_hash(f) is None


# ---------------------------------------------------------------------------
# write_if_changed
# ---------------------------------------------------------------------------


class TestWriteIfChanged:
    def test_writes_new_file(self, tmp_path):
        path = tmp_path / "lists" / "test.txt"
        result = write_if_changed(path, "Test (XX)", "IPv4", ["10.0.0.0/8"])
        assert result is True
        assert path.exists()
        text = path.read_text()
        assert "Country: Test (XX)" in text
        assert "Hash: sha256:" in text
        assert "10.0.0.0/8" in text

    def test_skips_when_hash_matches(self, tmp_path):
        path = tmp_path / "test.txt"
        write_if_changed(path, "Test", "IPv4", ["10.0.0.0/8"])
        mtime_before = path.stat().st_mtime
        time.sleep(0.05)
        result = write_if_changed(path, "Test", "IPv4", ["10.0.0.0/8"])
        assert result is False
        assert path.stat().st_mtime == mtime_before

    def test_updates_when_hash_differs(self, tmp_path):
        path = tmp_path / "test.txt"
        write_if_changed(path, "Test", "IPv4", ["10.0.0.0/8"])
        result = write_if_changed(path, "Test", "IPv4", ["172.16.0.0/12"])
        assert result is True
        assert "172.16.0.0/12" in path.read_text()

    def test_empty_lines(self, tmp_path):
        path = tmp_path / "test.txt"
        result = write_if_changed(path, "Test", "IPv4", [])
        assert result is True
        text = path.read_text()
        assert "Country: Test" in text
        assert "Hash: sha256:" in text


# ---------------------------------------------------------------------------
# write_text_if_changed
# ---------------------------------------------------------------------------


class TestWriteTextIfChanged:
    def test_writes_new(self, tmp_path):
        path = tmp_path / "sub" / "test.json"
        assert write_text_if_changed(path, '{"test": true}\n') is True
        assert path.read_text() == '{"test": true}\n'

    def test_skips_identical(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text("same")
        assert write_text_if_changed(path, "same") is False

    def test_updates_different(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text("old")
        assert write_text_if_changed(path, "new") is True
        assert path.read_text() == "new"


# ---------------------------------------------------------------------------
# load_overrides
# ---------------------------------------------------------------------------


class TestLoadOverrides:
    def test_reads_files(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path)

        adds = tmp_path / "xx.additions.txt"
        adds.write_text("# Test\n10.0.0.0/8\n")
        excs = tmp_path / "xx.exemptions.txt"
        excs.write_text("# Exc\n10.1.0.0/16\n")

        additions, exemptions = load_overrides("xx")
        assert len(additions) == 1
        assert additions[0] == (N("10.0.0.0/8"), "Test")
        assert len(exemptions) == 1

    def test_missing_files(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path)
        additions, exemptions = load_overrides("zz")
        assert additions == []
        assert exemptions == []


# ---------------------------------------------------------------------------
# process_country
# ---------------------------------------------------------------------------


class TestProcessCountry:
    def _make_entry(
        self, tmp_path, code="xx", name="Test", list_v4="Tv4", list_v6=None, v4=None, v6=None
    ):
        fetcher = MagicMock(
            return_value=(
                v4 if v4 is not None else [N("1.0.0.0/24"), N("2.0.0.0/24")],
                v6,
            )
        )
        entry = {"code": code, "name": name, "list_v4": list_v4, "fetch": fetcher}
        if list_v6:
            entry["list_v6"] = list_v6
        return entry

    def test_generates_v4_files(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        entry = self._make_entry(tmp_path)
        updates = process_country(entry)

        assert updates == 3
        assert (tmp_path / "lists" / "xx.ipv4.txt").exists()
        assert (tmp_path / "routeros" / "xx.ipv4.rsc").exists()
        assert (tmp_path / "sing-box" / "xx.ipv4.json").exists()
        assert not (tmp_path / "lists" / "xx.ipv6.txt").exists()
        assert not (tmp_path / "routeros" / "xx.ipv6.rsc").exists()

    def test_generates_v4_and_v6_files(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        entry = self._make_entry(
            tmp_path,
            list_v6="Tv6",
            v6=[ipaddress.ip_network("2001:db8::/32")],
        )
        updates = process_country(entry)

        assert updates == 6
        assert (tmp_path / "lists" / "xx.ipv6.txt").exists()
        assert (tmp_path / "routeros" / "xx.ipv6.rsc").exists()
        assert (tmp_path / "sing-box" / "xx.ipv6.json").exists()

    def test_no_update_on_same_data(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        entry = self._make_entry(tmp_path)
        process_country(entry)
        updates = process_country(entry)
        assert updates == 0

    def test_fetch_failure(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        entry = {
            "code": "xx",
            "name": "Test",
            "list_v4": "Tv4",
            "fetch": MagicMock(side_effect=Exception("network down")),
        }
        updates = process_country(entry)
        assert updates == 0

    def test_overrides_applied(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        (tmp_path / "overrides").mkdir()
        (tmp_path / "overrides" / "xx.additions.txt").write_text("# Extra\n172.16.0.0/12\n")

        entry = self._make_entry(tmp_path)
        process_country(entry)

        text = (tmp_path / "lists" / "xx.ipv4.txt").read_text()
        assert "172.16.0.0/12" in text

    def test_singbox_content(self, tmp_path, monkeypatch):
        import generate

        monkeypatch.setattr(generate, "LISTS_DIR", tmp_path / "lists")
        monkeypatch.setattr(generate, "ROUTEROS_DIR", tmp_path / "routeros")
        monkeypatch.setattr(generate, "SINGBOX_DIR", tmp_path / "sing-box")
        monkeypatch.setattr(generate, "OVERRIDES_DIR", tmp_path / "overrides")

        entry = self._make_entry(tmp_path)
        process_country(entry)

        sb = json.loads((tmp_path / "sing-box" / "xx.ipv4.json").read_text())
        assert "1.0.0.0/24" in sb["rules"][0]["ip_cidr"]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    @patch("generate.process_country")
    def test_processes_all_countries(self, mock_process):
        mock_process.return_value = 1
        from generate import COUNTRIES, main

        main()
        assert mock_process.call_count == len(COUNTRIES)

    @patch("generate.process_country")
    def test_one_failure_doesnt_stop_others(self, mock_process):
        mock_process.side_effect = [0, 3, 2]
        from generate import main

        main()
        assert mock_process.call_count == 3
