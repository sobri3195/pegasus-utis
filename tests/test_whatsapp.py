"""Tests for WhatsApp analyzer."""

import tempfile
from pathlib import Path

from utis.modules.whatsapp.analyzer import WhatsAppAnalyzer


def test_whatsapp_parsing():
    chat = """12/31/20, 10:30 PM - Alice: Hello
12/31/20, 10:31 PM - Bob: Hi
12/31/20, 10:35 PM - Alice: How are you?
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "chat.txt"
        p.write_text(chat, encoding="utf-8")

        analyzer = WhatsAppAnalyzer()
        result = analyzer.analyze(str(p))

        assert result.parsed_messages == 3
        assert "Alice" in result.participants
        assert "Bob" in result.participants
