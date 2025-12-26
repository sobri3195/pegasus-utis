"""Tests for email analyzer."""

import tempfile
from pathlib import Path

from utis.modules.email.analyzer import EmailAnalyzer


def test_email_parsing_and_urls():
    eml = """From: Test <test@example.com>
Return-Path: <bounce@example.com>
Message-ID: <abc123@example.com>
Authentication-Results: spf=pass dkim=pass dmarc=pass

Hello, click https://example.com/login to continue.
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "msg.eml"
        p.write_text(eml, encoding="utf-8")

        analyzer = EmailAnalyzer()
        result = analyzer.analyze(str(p))

        assert result.headers["From"]
        assert "https://example.com/login" in result.urls
        assert result.overall_risk_score >= 0
