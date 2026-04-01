"""Tests for fetch_cn — chnroutes2 download."""

from unittest.mock import patch

import pytest


class TestFetchCn:
    @patch("fetch_cn.fetch_text")
    def test_valid_response(self, mock_fetch_text):
        mock_fetch_text.return_value = "1.0.0.0/24\n223.5.5.5/32\n"
        from fetch_cn import fetch

        v4, v6 = fetch()
        assert len(v4) == 2
        assert v6 is None

    @patch("fetch_cn.fetch_text")
    def test_empty_response(self, mock_fetch_text):
        mock_fetch_text.return_value = ""
        from fetch_cn import fetch

        v4, v6 = fetch()
        assert v4 == []
        assert v6 is None

    @patch("fetch_cn.fetch_text")
    def test_invalid_lines_skipped(self, mock_fetch_text):
        mock_fetch_text.return_value = "1.0.0.0/24\ngarbage\n"
        from fetch_cn import fetch

        v4, _ = fetch()
        assert len(v4) == 1

    @patch("fetch_cn.fetch_text")
    def test_network_error(self, mock_fetch_text):
        mock_fetch_text.side_effect = Exception("DNS failure")
        from fetch_cn import fetch

        with pytest.raises(Exception, match="DNS failure"):
            fetch()
