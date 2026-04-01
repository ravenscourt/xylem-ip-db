"""Tests for utils.py — data transformations and HTTP fetch helpers."""

import ipaddress
import json
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from utils import (
    apply_overrides,
    build_routeros_lines,
    build_singbox_ruleset,
    content_hash,
    fetch_json,
    fetch_text,
    fetch_url,
    parse_cidr_text,
)

N = ipaddress.ip_network


# ---------------------------------------------------------------------------
# fetch_url / fetch_json / fetch_text
# ---------------------------------------------------------------------------


class TestFetchUrl:
    @patch("utils.urllib.request.urlopen")
    def test_success_first_try(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"hello"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = fetch_url("http://example.com")
        assert result == b"hello"
        assert mock_urlopen.call_count == 1

    @patch("utils.time.sleep")
    @patch("utils.urllib.request.urlopen")
    def test_retry_on_transient_failure(self, mock_urlopen, mock_sleep):
        resp = MagicMock()
        resp.read.return_value = b"ok"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            resp,
        ]

        result = fetch_url("http://example.com", retries=3, backoff_base=1.0)
        assert result == b"ok"
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("utils.time.sleep")
    @patch("utils.urllib.request.urlopen")
    def test_all_retries_exhausted(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = Exception("always fails")

        with pytest.raises(Exception, match="always fails"):
            fetch_url("http://example.com", retries=3, backoff_base=0.5)

        assert mock_urlopen.call_count == 4  # 1 initial + 3 retries
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("utils.time.sleep")
    @patch("utils.urllib.request.urlopen")
    def test_backoff_increases_exponentially(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = Exception("nope")

        with pytest.raises(Exception):
            fetch_url("http://example.com", retries=3, backoff_base=2.0)

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [2.0, 4.0, 8.0]

    @patch("utils.urllib.request.urlopen")
    def test_no_retries_raises_immediately(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("fail")

        with pytest.raises(Exception, match="fail"):
            fetch_url("http://example.com", retries=0)

        assert mock_urlopen.call_count == 1


class TestFetchJson:
    @patch("utils.urllib.request.urlopen")
    def test_parses_json(self, mock_urlopen):
        data = {"key": "value", "num": 42}
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = fetch_json("http://example.com/api")
        assert result == data

    @patch("utils.urllib.request.urlopen")
    def test_invalid_json_raises(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"not json"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with pytest.raises(json.JSONDecodeError):
            fetch_json("http://example.com/api")


class TestFetchText:
    @patch("utils.urllib.request.urlopen")
    def test_returns_string(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = "hello world".encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = fetch_text("http://example.com")
        assert result == "hello world"
        assert isinstance(result, str)

    @patch("utils.urllib.request.urlopen")
    def test_utf8_decoding(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = "café résumé".encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = fetch_text("http://example.com")
        assert result == "café résumé"


# ---------------------------------------------------------------------------
# parse_cidr_text
# ---------------------------------------------------------------------------


class TestParseCidrText:
    def test_basic_ranges_with_reasons(self):
        text = textwrap.dedent("""\
            # Header comment
            # Description line

            # Reason A
            10.0.0.0/8
            192.168.0.0/16

            # Reason B
            172.16.0.0/12
        """)
        result = parse_cidr_text(text)
        assert result == [
            (N("10.0.0.0/8"), "Reason A"),
            (N("192.168.0.0/16"), "Reason A"),
            (N("172.16.0.0/12"), "Reason B"),
        ]

    def test_blank_line_resets_reason(self):
        text = "# My Reason\n10.0.0.0/8\n\n192.168.0.0/16\n"
        result = parse_cidr_text(text)
        assert result[0] == (N("10.0.0.0/8"), "My Reason")
        assert result[1] == (N("192.168.0.0/16"), None)

    def test_header_comments_dont_leak(self):
        text = "# File header\n# Another header line\n\n# Actual reason\n10.0.0.0/8\n"
        result = parse_cidr_text(text)
        assert result == [(N("10.0.0.0/8"), "Actual reason")]

    def test_invalid_range_skipped(self):
        text = "not-a-cidr\n10.0.0.0/8\n"
        result = parse_cidr_text(text)
        assert len(result) == 1
        assert result[0][0] == N("10.0.0.0/8")

    def test_empty_text(self):
        assert parse_cidr_text("") == []

    def test_strict_false_host_bits(self):
        result = parse_cidr_text("10.0.0.1/8\n")
        assert result[0][0] == N("10.0.0.0/8")

    def test_only_comments(self):
        text = "# Just comments\n# Nothing else\n"
        assert parse_cidr_text(text) == []

    def test_bare_hash(self):
        text = "#\n10.0.0.0/8\n"
        result = parse_cidr_text(text)
        assert result == [(N("10.0.0.0/8"), None)]

    def test_consecutive_comments_last_wins(self):
        text = "# First\n# Second\n# Third\n10.0.0.0/8\n"
        result = parse_cidr_text(text)
        assert result == [(N("10.0.0.0/8"), "Third")]


# ---------------------------------------------------------------------------
# apply_overrides
# ---------------------------------------------------------------------------


class TestApplyOverrides:
    def test_no_overrides(self):
        nets = [N("10.0.0.0/8"), N("192.168.0.0/16")]
        lines = apply_overrides(nets, [], [])
        ranges = [x for x in lines if not x.startswith("#")]
        assert "10.0.0.0/8" in ranges
        assert "192.168.0.0/16" in ranges

    def test_additions_with_reason(self):
        nets = [N("10.0.0.0/8")]
        adds = [(N("172.16.0.0/12"), "Private range")]
        lines = apply_overrides(nets, adds, [])
        assert "# Private range" in lines
        assert "172.16.0.0/12" in lines

    def test_additions_comment_per_entry(self):
        nets = []
        adds = [
            (N("10.0.0.0/8"), "Private"),
            (N("172.16.0.0/12"), "Private"),
            (N("192.168.0.0/16"), "Also private"),
        ]
        lines = apply_overrides(nets, adds, [])
        comment_lines = [x for x in lines if x.startswith("#")]
        assert comment_lines.count("# Private") == 2
        assert "# Also private" in comment_lines

    def test_addition_merged_with_ripe_no_annotation(self):
        nets = [N("10.0.0.0/9")]
        adds = [(N("10.128.0.0/9"), "Should merge")]
        lines = apply_overrides(nets, adds, [])
        ranges = [x for x in lines if not x.startswith("#")]
        assert "10.0.0.0/8" in ranges
        assert len([x for x in lines if x.startswith("#")]) == 0

    def test_single_exemption(self):
        nets = [N("10.0.0.0/8")]
        exemptions = [(N("10.1.0.0/16"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        for r in ranges:
            assert not ipaddress.ip_network(r).overlaps(N("10.1.0.0/16"))
        comments = [x for x in lines if x.startswith("#")]
        assert any("10.1.0.0/16" in c and "10.0.0.0/8" in c for c in comments)

    def test_exemption_fragment_numbering(self):
        nets = [N("10.0.0.0/24")]
        exemptions = [(N("10.0.0.128/25"), None)]
        lines = apply_overrides(nets, [], exemptions)
        comments = [x for x in lines if x.startswith("#")]
        assert any("fragment 1/" in c for c in comments)

    def test_single_ip_exemption(self):
        nets = [N("10.0.0.0/24")]
        exemptions = [(N("10.0.0.5/32"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        all_nets = [ipaddress.ip_network(r) for r in ranges]
        covered = set()
        for n in all_nets:
            for addr in n:
                covered.add(addr)
        assert ipaddress.ip_address("10.0.0.5") not in covered
        assert ipaddress.ip_address("10.0.0.4") in covered
        assert ipaddress.ip_address("10.0.0.6") in covered

    def test_single_ip_exemption_fragment_count(self):
        nets = [N("10.0.0.0/24")]
        exemptions = [(N("10.0.0.5/32"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        assert len(ranges) == 8

    def test_exemption_fully_covers_range(self):
        nets = [N("10.0.0.0/24"), N("192.168.0.0/16")]
        exemptions = [(N("10.0.0.0/24"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        assert "10.0.0.0/24" not in ranges
        assert "192.168.0.0/16" in ranges

    def test_multiple_exemptions_same_parent(self):
        nets = [N("10.0.0.0/8")]
        exemptions = [
            (N("10.1.0.0/16"), None),
            (N("10.2.0.0/16"), None),
        ]
        lines = apply_overrides(nets, [], exemptions)
        comments = [x for x in lines if x.startswith("#")]
        merged = [c for c in comments if "10.1.0.0/16" in c and "10.2.0.0/16" in c]
        assert len(merged) > 0

    def test_addition_with_exemption(self):
        nets = [N("10.0.0.0/8")]
        adds = [(N("192.168.0.0/16"), "Custom")]
        exemptions = [(N("10.1.0.0/16"), None)]
        lines = apply_overrides(nets, adds, exemptions)
        assert "# Custom" in lines
        assert "192.168.0.0/16" in lines
        ranges = [x for x in lines if not x.startswith("#")]
        assert "10.1.0.0/16" not in ranges

    def test_exemption_with_reason_from_addition(self):
        nets = []
        adds = [(N("10.0.0.0/8"), "My Range")]
        exemptions = [(N("10.1.0.0/16"), None)]
        lines = apply_overrides(nets, adds, exemptions)
        comments = [x for x in lines if x.startswith("#")]
        assert any("My Range" in c for c in comments)

    def test_ipv6_ranges(self):
        nets = [ipaddress.ip_network("2001:db8::/32")]
        adds = [(ipaddress.ip_network("fd00::/8"), "v6 add")]
        lines = apply_overrides(nets, adds, [])
        ranges = [x for x in lines if not x.startswith("#")]
        assert "2001:db8::/32" in ranges
        assert "fd00::/8" in ranges

    def test_empty_networks_with_exemptions(self):
        lines = apply_overrides([], [], [(N("10.0.0.0/8"), None)])
        assert lines == []

    def test_non_overlapping_exemption_noop(self):
        nets = [N("192.168.0.0/16")]
        exemptions = [(N("10.0.0.0/8"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        assert ranges == ["192.168.0.0/16"]

    def test_duplicate_addition(self):
        nets = [N("10.0.0.0/8")]
        adds = [(N("10.0.0.0/8"), "Duplicate")]
        lines = apply_overrides(nets, adds, [])
        ranges = [x for x in lines if not x.startswith("#")]
        assert ranges.count("10.0.0.0/8") == 1

    def test_overlapping_additions_collapse(self):
        nets = []
        adds = [
            (N("10.0.0.0/24"), "A"),
            (N("10.0.1.0/24"), "B"),
            (N("10.0.0.0/23"), "C"),
        ]
        lines = apply_overrides(nets, adds, [])
        ranges = [x for x in lines if not x.startswith("#")]
        assert "10.0.0.0/23" in ranges
        assert len(ranges) == 1

    def test_exempt_everything(self):
        nets = [N("10.0.0.0/8")]
        exemptions = [(N("10.0.0.0/8"), None)]
        lines = apply_overrides(nets, [], exemptions)
        ranges = [x for x in lines if not x.startswith("#")]
        assert ranges == []


# ---------------------------------------------------------------------------
# build_routeros_lines
# ---------------------------------------------------------------------------


class TestBuildRouterosLines:
    def test_ipv4_prefix(self):
        lines = build_routeros_lines(["10.0.0.0/8"], "IRv4", 4)
        assert any("/ip firewall" in x for x in lines)
        assert any("list=IRv4" in x for x in lines)

    def test_ipv6_prefix(self):
        lines = build_routeros_lines(["2001:db8::/32"], "IRv6", 6)
        assert any("/ipv6 firewall" in x for x in lines)
        assert any("list=IRv6" in x for x in lines)

    def test_comment_becomes_attribute(self):
        lines = build_routeros_lines(["# Shecan", "10.0.0.0/8"], "X", 4)
        add_lines = [x for x in lines if x.startswith(":do")]
        assert len(add_lines) == 1
        assert 'comment="Shecan"' in add_lines[0]

    def test_comment_cleared_after_use(self):
        lines = build_routeros_lines(
            ["# ISP", "10.0.0.0/8", "172.16.0.0/12", "# Other", "192.168.0.0/16"], "X", 4
        )
        add_lines = [x for x in lines if x.startswith(":do")]
        assert 'comment="ISP"' in add_lines[0]
        assert "comment" not in add_lines[1]
        assert 'comment="Other"' in add_lines[2]

    def test_empty_line_clears_comment(self):
        lines = build_routeros_lines(["# Header", "", "10.0.0.0/8"], "X", 4)
        add_lines = [x for x in lines if x.startswith(":do")]
        assert len(add_lines) == 1
        assert "comment" not in add_lines[0]

    def test_no_comment_no_attribute(self):
        lines = build_routeros_lines(["10.0.0.0/8"], "IRv4", 4)
        add_lines = [x for x in lines if x.startswith(":do")]
        assert len(add_lines) == 1
        assert "comment" not in add_lines[0]
        assert "address=10.0.0.0/8" in add_lines[0]
        assert "list=IRv4" in add_lines[0]


# ---------------------------------------------------------------------------
# build_singbox_ruleset
# ---------------------------------------------------------------------------


class TestBuildSingboxRuleset:
    def test_valid_json(self):
        result = build_singbox_ruleset(["10.0.0.0/8", "172.16.0.0/12"])
        data = json.loads(result)
        assert data["version"] == 2
        assert data["rules"][0]["ip_cidr"] == ["10.0.0.0/8", "172.16.0.0/12"]

    def test_comments_filtered(self):
        result = build_singbox_ruleset(["# comment", "10.0.0.0/8", "# another"])
        data = json.loads(result)
        assert data["rules"][0]["ip_cidr"] == ["10.0.0.0/8"]

    def test_empty_input(self):
        result = build_singbox_ruleset([])
        data = json.loads(result)
        assert data["rules"][0]["ip_cidr"] == []


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_comments_excluded(self):
        h1 = content_hash(["# comment", "10.0.0.0/8"])
        h2 = content_hash(["10.0.0.0/8"])
        assert h1 == h2

    def test_different_ranges_different_hash(self):
        h1 = content_hash(["10.0.0.0/8"])
        h2 = content_hash(["172.16.0.0/12"])
        assert h1 != h2

    def test_deterministic(self):
        h1 = content_hash(["10.0.0.0/8", "172.16.0.0/12"])
        h2 = content_hash(["10.0.0.0/8", "172.16.0.0/12"])
        assert h1 == h2
