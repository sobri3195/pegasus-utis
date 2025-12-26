from utis.modules.whatsapp.analyzer import parse_chat


def test_parse_chat_messages():
    content = "12/01/24, 08:00 - Alice: Hi\n"
    messages = parse_chat(content)
    assert len(messages) == 1
    assert messages[0].sender == "Alice"
