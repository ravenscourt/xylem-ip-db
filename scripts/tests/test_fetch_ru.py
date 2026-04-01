"""Tests for fetch_ru — antifilter download."""

from unittest.mock import patch

import pytest


class TestFetchRu:
    @patch("fetch_ru.fetch_text")
    def test_valid_response(self, mock_fetch_text):
        mock_fetch_text.return_value = "1.0.0.0/24\n2.0.0.0/16\n10.0.0.0/8\n"
        from fetch_ru import fetch

        v4, v6 = fetch()
        assert len(v4) == 3
        assert v6 is None

    @patch("fetch_ru.fetch_text")
    def test_empty_response(self, mock_fetch_text):
        mock_fetch_text.return_value = ""
        from fetch_ru import fetch

        v4, v6 = fetch()
        assert v4 == []
        assert v6 is None

    @patch("fetch_ru.fetch_text")
    def test_comments_and_blanks_skipped(self, mock_fetch_text):
        mock_fetch_text.return_value = "# header\n\n1.0.0.0/24\n# comment\n2.0.0.0/16\n"
        from fetch_ru import fetch

        v4, _ = fetch()
        assert len(v4) == 2

    @patch("fetch_ru.fetch_text")
    def test_invalid_lines_skipped(self, mock_fetch_text):
        mock_fetch_text.return_value = "1.0.0.0/24\nnot-a-cidr\n2.0.0.0/16\n"
        from fetch_ru import fetch

        v4, _ = fetch()
        assert len(v4) == 2

    @patch("fetch_ru.fetch_text")
    def test_network_error(self, mock_fetch_text):
        mock_fetch_text.side_effect = Exception("timeout")
        from fetch_ru import fetch

        with pytest.raises(Exception, match="timeout"):
            fetch()
