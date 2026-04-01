"""Tests for validate_issue.py — issue parsing and range validation."""

import ipaddress
import json
import textwrap

import pytest

from validate_issue import (
    discover_countries,
    load_ranges,
    parse_issue_body,
    validate_addition,
    validate_exemption,
)

N = ipaddress.ip_network


# ---------------------------------------------------------------------------
# discover_countries
# ---------------------------------------------------------------------------


class TestDiscoverCountries:
    def test_finds_countries(self, tmp_path, monkeypatch):
        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", tmp_path)

        (tmp_path / "ir.ipv4.txt").write_text("# test\n")
        (tmp_path / "ir.ipv6.txt").write_text("# test\n")
        (tmp_path / "ru.ipv4.txt").write_text("# test\n")

        result = discover_countries()
        assert result == {"ir", "ru"}

    def test_empty_dir(self, tmp_path, monkeypatch):
        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", tmp_path)
        assert discover_countries() == set()

    def test_missing_dir(self, tmp_path, monkeypatch):
        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", tmp_path / "nope")
        assert discover_countries() == set()

    def test_ignores_non_matching_files(self, tmp_path, monkeypatch):
        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", tmp_path)

        (tmp_path / "ir.ipv4.txt").write_text("# test\n")
        (tmp_path / "readme.txt").write_text("# ignore\n")
        (tmp_path / "data.json").write_text("{}")

        assert discover_countries() == {"ir"}


# ---------------------------------------------------------------------------
# parse_issue_body
# ---------------------------------------------------------------------------


class TestParseIssueBody:
    def test_basic_fields(self):
        body = textwrap.dedent("""\
            ### Country

            IR - Iran

            ### IP or CIDR Range

            10.0.0.0/8

            ### Reason

            Testing purposes
        """)
        fields = parse_issue_body(body)
        assert fields["country"] == "IR - Iran"
        assert fields["ip or cidr range"] == "10.0.0.0/8"
        assert fields["reason"] == "Testing purposes"

    def test_multiline_reason(self):
        body = "### Reason\n\nLine one\nLine two\nLine three"
        fields = parse_issue_body(body)
        assert "Line one" in fields["reason"]
        assert "Line three" in fields["reason"]

    def test_empty_body(self):
        assert parse_issue_body("") == {}

    def test_no_sections(self):
        assert parse_issue_body("Just some text\nwithout headers") == {}

    def test_keys_lowercased(self):
        body = "### My Field\n\nvalue"
        fields = parse_issue_body(body)
        assert "my field" in fields


# ---------------------------------------------------------------------------
# load_ranges
# ---------------------------------------------------------------------------


class TestLoadRanges:
    def test_loads_from_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("# Header\n# Hash: sha256:abc\n10.0.0.0/8\n192.168.0.0/16\n")
        result = load_ranges(f)
        assert result == [N("10.0.0.0/8"), N("192.168.0.0/16")]

    def test_missing_file(self, tmp_path):
        assert load_ranges(tmp_path / "missing.txt") == []

    def test_skips_comments_and_blanks(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("# comment\n\n10.0.0.0/8\n# another\n")
        result = load_ranges(f)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# validate_addition
# ---------------------------------------------------------------------------


class TestValidateAddition:
    def test_already_covered(self):
        existing = [N("10.0.0.0/8")]
        result = validate_addition(N("10.1.0.0/16"), existing)
        assert result is not None
        assert "already included" in result

    def test_partial_overlap(self):
        existing = [N("10.0.0.0/16")]
        result = validate_addition(N("10.0.0.0/8"), existing)
        assert result is not None
        assert "overlaps" in result

    def test_no_overlap_valid(self):
        existing = [N("10.0.0.0/8")]
        result = validate_addition(N("172.16.0.0/12"), existing)
        assert result is None

    def test_empty_existing(self):
        assert validate_addition(N("10.0.0.0/8"), []) is None


# ---------------------------------------------------------------------------
# validate_exemption
# ---------------------------------------------------------------------------


class TestValidateExemption:
    def test_range_absent(self):
        existing = [N("10.0.0.0/8")]
        result = validate_exemption(N("172.16.0.0/12"), existing)
        assert result is not None
        assert "not present" in result

    def test_range_present(self):
        existing = [N("10.0.0.0/8")]
        result = validate_exemption(N("10.1.0.0/16"), existing)
        assert result is None

    def test_empty_existing(self):
        result = validate_exemption(N("10.0.0.0/8"), [])
        assert result is not None
        assert "not present" in result


# ---------------------------------------------------------------------------
# main (integration)
# ---------------------------------------------------------------------------


class TestMain:
    @staticmethod
    def _issue_body(country, cidr, reason="Test"):
        return (
            f"### Country\n\n{country}\n\n### IP or CIDR Range\n\n{cidr}\n\n### Reason\n\n{reason}"
        )

    def _make_event(self, tmp_path, labels, body, title="Test"):
        event = {
            "issue": {
                "title": title,
                "body": body,
                "labels": [{"name": lb} for lb in labels],
            }
        }
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event))
        return str(event_file)

    def _setup_lists(self, tmp_path, monkeypatch, country="ir", ranges=None):
        """Create fake list files and point LISTS_DIR to them."""
        lists_dir = tmp_path / "lists"
        lists_dir.mkdir(exist_ok=True)
        if ranges is None:
            ranges = ["10.0.0.0/8"]
        content = "# Header\n" + "\n".join(ranges) + "\n"
        (lists_dir / f"{country}.ipv4.txt").write_text(content)

        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", lists_dir)
        return lists_dir

    def test_addition_already_covered(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("IR - Iran", "10.1.0.0/16")
        event_path = self._make_event(tmp_path, ["addition"], body)
        self._setup_lists(tmp_path, monkeypatch)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        validate_issue.main()
        assert "already included" in capsys.readouterr().out

    def test_addition_valid(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("IR - Iran", "172.16.0.0/12")
        event_path = self._make_event(tmp_path, ["addition"], body)
        self._setup_lists(tmp_path, monkeypatch)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        validate_issue.main()
        assert "not yet in the list" in capsys.readouterr().out

    def test_exemption_not_present(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("IR - Iran", "172.16.0.0/12")
        event_path = self._make_event(tmp_path, ["exemption"], body)
        self._setup_lists(tmp_path, monkeypatch)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        validate_issue.main()
        assert "not present" in capsys.readouterr().out

    def test_exemption_valid(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("IR - Iran", "10.1.0.0/16")
        event_path = self._make_event(tmp_path, ["exemption"], body)
        self._setup_lists(tmp_path, monkeypatch)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        validate_issue.main()
        assert "request looks valid" in capsys.readouterr().out

    def test_unknown_country(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("XX - Unknown", "10.0.0.0/8")
        event_path = self._make_event(tmp_path, ["addition"], body)
        self._setup_lists(tmp_path, monkeypatch, country="ir")

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        with pytest.raises(SystemExit) as exc_info:
            validate_issue.main()
        assert exc_info.value.code == 0
        assert "Unknown country" in capsys.readouterr().out

    def test_invalid_cidr(self, tmp_path, monkeypatch, capsys):
        body = "### Country\n\nIR - Iran\n\n### IP or CIDR Range\n\nnot-valid\n\n### Reason\n\nTest"
        event_path = self._make_event(tmp_path, ["addition"], body)
        self._setup_lists(tmp_path, monkeypatch)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        with pytest.raises(SystemExit) as exc_info:
            validate_issue.main()
        assert exc_info.value.code == 0
        assert "not a valid" in capsys.readouterr().out

    def test_missing_fields(self, tmp_path, monkeypatch, capsys):
        body = "### Country\n\nIR - Iran"
        event_path = self._make_event(tmp_path, ["addition"], body)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        with pytest.raises(SystemExit) as exc_info:
            validate_issue.main()
        assert exc_info.value.code == 0
        assert "Could not parse" in capsys.readouterr().out

    def test_no_relevant_labels(self, tmp_path, monkeypatch):
        body = "### Country\n\nIR\n\n### IP or CIDR Range\n\n10.0.0.0/8"
        event_path = self._make_event(tmp_path, ["bug"], body)

        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)
        import validate_issue

        with pytest.raises(SystemExit) as exc_info:
            validate_issue.main()
        assert exc_info.value.code == 0

    def test_ipv6_range(self, tmp_path, monkeypatch, capsys):
        body = self._issue_body("IR - Iran", "2001:db8::/32")
        event_path = self._make_event(tmp_path, ["addition"], body)

        lists_dir = tmp_path / "lists"
        lists_dir.mkdir(exist_ok=True)
        (lists_dir / "ir.ipv4.txt").write_text("# H\n10.0.0.0/8\n")
        (lists_dir / "ir.ipv6.txt").write_text("# H\n2001:db8::/32\n")

        import validate_issue

        monkeypatch.setattr(validate_issue, "LISTS_DIR", lists_dir)
        monkeypatch.setenv("GITHUB_EVENT_PATH", event_path)

        validate_issue.main()
        assert "already included" in capsys.readouterr().out
