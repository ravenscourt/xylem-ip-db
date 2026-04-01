"""Tests for fetch_ir — ASN-based RIPE resolution."""

import ipaddress
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from fetch_ir import _is_active

# ---------------------------------------------------------------------------
# _is_active (week-overlap logic)
# ---------------------------------------------------------------------------


class TestIsActive:
    NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)  # Wednesday

    def test_timeline_covering_now(self):
        tl = [{"starttime": "2026-03-01T00:00:00", "endtime": "2026-04-15T00:00:00"}]
        assert _is_active(tl, self.NOW) is True

    def test_timeline_ending_today_early(self):
        tl = [{"starttime": "2026-03-18T08:00:00", "endtime": "2026-04-01T08:00:00"}]
        assert _is_active(tl, self.NOW) is True

    def test_timeline_ending_on_week_start(self):
        tl = [{"starttime": "2026-03-20T00:00:00", "endtime": "2026-03-30T08:00:00"}]
        assert _is_active(tl, self.NOW) is True

    def test_timeline_before_this_week(self):
        tl = [{"starttime": "2026-01-01T00:00:00", "endtime": "2026-03-29T23:59:59"}]
        assert _is_active(tl, self.NOW) is False

    def test_timeline_after_this_week(self):
        week_end = self.NOW - timedelta(days=self.NOW.weekday()) + timedelta(days=7)
        start = week_end + timedelta(days=1)
        end = start + timedelta(days=7)
        tl = [{"starttime": start.isoformat(), "endtime": end.isoformat()}]
        assert _is_active(tl, self.NOW) is False

    def test_empty_timelines(self):
        assert _is_active([], self.NOW) is False

    def test_multiple_timelines_one_active(self):
        tl = [
            {"starttime": "2026-01-01T00:00:00", "endtime": "2026-02-01T00:00:00"},
            {"starttime": "2026-03-30T00:00:00", "endtime": "2026-04-02T00:00:00"},
        ]
        assert _is_active(tl, self.NOW) is True

    def test_multiple_timelines_none_active(self):
        tl = [
            {"starttime": "2026-01-01T00:00:00", "endtime": "2026-02-01T00:00:00"},
            {"starttime": "2025-06-01T00:00:00", "endtime": "2025-07-01T00:00:00"},
        ]
        assert _is_active(tl, self.NOW) is False


# ---------------------------------------------------------------------------
# fetch()
# ---------------------------------------------------------------------------


class TestFetchIr:
    NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _country_asns_response(self, asns):
        routed = ", ".join(f"AsnSingle({a})" for a in asns)
        return {
            "data": {
                "countries": [
                    {
                        "resource": "IR",
                        "routed": f"{{{routed}}}",
                    }
                ]
            }
        }

    def _prefixes_response(self, prefixes):
        """Build a mock announced-prefixes response.
        Each item in ``prefixes`` is (prefix_str, active_bool).
        Active entries get a timeline overlapping NOW's week;
        inactive ones get an expired range well before this week.
        """
        entries = []
        for prefix, active in prefixes:
            if active:
                tl = [
                    {
                        "starttime": "2026-03-01T00:00:00",
                        "endtime": "2026-04-15T00:00:00",
                    }
                ]
            else:
                tl = [
                    {
                        "starttime": "2026-01-01T00:00:00",
                        "endtime": "2026-02-01T00:00:00",
                    }
                ]
            entries.append({"prefix": prefix, "timelines": tl})
        return {"data": {"prefixes": entries}}

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_valid_response(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([12345, 67890]),
            self._prefixes_response(
                [
                    ("1.0.0.0/24", True),
                    ("2.0.0.0/16", True),
                ]
            ),
            self._prefixes_response(
                [
                    ("3.0.0.0/8", True),
                    ("2001:db8::/32", True),
                ]
            ),
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert len(v4) == 3
        assert ipaddress.ip_network("1.0.0.0/24") in v4
        assert len(v6) == 1
        assert ipaddress.ip_network("2001:db8::/32") in v6

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_timeline_filtering(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([11111]),
            self._prefixes_response(
                [
                    ("1.0.0.0/24", True),
                    ("2.0.0.0/24", False),
                    ("3.0.0.0/24", True),
                ]
            ),
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert len(v4) == 2
        assert ipaddress.ip_network("1.0.0.0/24") in v4
        assert ipaddress.ip_network("3.0.0.0/24") in v4
        assert ipaddress.ip_network("2.0.0.0/24") not in v4

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_ripe_boundary_endtime(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([44244]),
            {
                "data": {
                    "prefixes": [
                        {
                            "prefix": "2.145.80.0/20",
                            "timelines": [
                                {
                                    "starttime": "2026-03-18T08:00:00",
                                    "endtime": "2026-04-01T08:00:00",
                                }
                            ],
                        }
                    ]
                }
            },
        ]

        from fetch_ir import fetch

        v4, _ = fetch()
        assert ipaddress.ip_network("2.145.80.0/20") in v4

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_empty_asn_list(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW

        mock_fetch_json.return_value = self._country_asns_response([])

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert v4 == []
        assert v6 == []
        assert mock_fetch_json.call_count == 1

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_single_asn_failure_does_not_break_others(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([111, 222]),
            Exception("AS111 timeout"),
            self._prefixes_response([("5.0.0.0/24", True)]),
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert len(v4) == 1
        assert ipaddress.ip_network("5.0.0.0/24") in v4

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.fetch_json")
    def test_country_asns_network_error(self, mock_fetch_json, mock_sleep):
        mock_fetch_json.side_effect = Exception("Connection refused")

        from fetch_ir import fetch

        with pytest.raises(Exception, match="Connection refused"):
            fetch()

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_ipv6_only_asn(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([99999]),
            self._prefixes_response(
                [
                    ("2001:db8::/32", True),
                    ("fd00::/8", True),
                ]
            ),
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert v4 == []
        assert len(v6) == 2

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_duplicate_prefixes_returned_raw(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([100, 200]),
            self._prefixes_response([("10.0.0.0/24", True)]),
            self._prefixes_response([("10.0.0.0/24", True), ("10.0.1.0/24", True)]),
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert len(v4) == 3
        assert ipaddress.ip_network("10.0.0.0/24") in v4
        assert ipaddress.ip_network("10.0.1.0/24") in v4

    @patch("fetch_ir.time.sleep")
    @patch("fetch_ir.datetime")
    @patch("fetch_ir.fetch_json")
    def test_empty_timelines_excluded(self, mock_fetch_json, mock_dt, mock_sleep):
        mock_dt.now.return_value = self.NOW
        mock_dt.fromisoformat = datetime.fromisoformat

        mock_fetch_json.side_effect = [
            self._country_asns_response([55555]),
            {
                "data": {
                    "prefixes": [
                        {"prefix": "1.0.0.0/24", "timelines": []},
                    ]
                }
            },
        ]

        from fetch_ir import fetch

        v4, v6 = fetch()
        assert v4 == []
        assert v6 == []
