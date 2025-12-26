from pathlib import Path

from utis.modules.email.analyzer import analyze_email


def test_analyze_email_extracts_url(tmp_path: Path):
    sample = "From: test@example.com\n\nClick https://example.com"
    file_path = tmp_path / "sample.txt"
    file_path.write_text(sample, encoding="utf-8")
    report = analyze_email(file_path)
    assert "https://example.com" in report["urls"]
