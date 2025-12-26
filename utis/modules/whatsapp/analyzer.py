from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
from dateutil import parser as date_parser

from utis.core.events import EventProcessor
from utis.core.models import Event

MESSAGE_REGEX = re.compile(r"^(.+?) - (.*?): (.*)$")
DATE_SEPARATORS = ["/", ".", "-"]
STOPWORDS = {"dan", "yang", "di", "ke", "the", "a", "i", "you"}


@dataclass
class Message:
    timestamp: datetime
    sender: str
    text: str


def _parse_datetime(raw: str) -> Optional[datetime]:
    for sep in DATE_SEPARATORS:
        if sep in raw:
            try:
                return date_parser.parse(raw, dayfirst=True)
            except (ValueError, OverflowError):
                continue
    return None


def parse_chat(text: str) -> List[Message]:
    messages: List[Message] = []
    for line in text.splitlines():
        match = MESSAGE_REGEX.match(line)
        if not match:
            continue
        raw_ts, sender, text_msg = match.groups()
        timestamp = _parse_datetime(raw_ts)
        if timestamp:
            messages.append(Message(timestamp=timestamp, sender=sender, text=text_msg))
    return messages


def compute_stats(messages: List[Message]) -> Dict[str, Any]:
    per_day = Counter(msg.timestamp.date().isoformat() for msg in messages)
    per_hour = Counter(msg.timestamp.hour for msg in messages)
    words = Counter()
    for msg in messages:
        for word in re.findall(r"\b\w+\b", msg.text.lower()):
            if word not in STOPWORDS:
                words[word] += 1
    top_words = words.most_common(10)
    response_times = []
    last_by_sender: Dict[str, datetime] = {}
    for msg in messages:
        for sender, last_time in last_by_sender.items():
            if sender != msg.sender:
                response_times.append((msg.timestamp - last_time).total_seconds())
                break
        last_by_sender[msg.sender] = msg.timestamp
    response_avg = mean(response_times) if response_times else None
    anomaly_days = []
    counts = list(per_day.values())
    if counts:
        avg = mean(counts)
        std = pstdev(counts) if len(counts) > 1 else 0
        for day, count in per_day.items():
            if std > 0 and (count - avg) / std > 2:
                anomaly_days.append({"date": day, "count": count})
    return {
        "messages_total": len(messages),
        "messages_per_day": dict(per_day),
        "active_hours": dict(per_hour),
        "top_words": top_words,
        "avg_response_seconds": response_avg,
        "anomaly_days": anomaly_days,
    }


def export_reports(stats: Dict[str, Any], export_dir: Path) -> Tuple[Path, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "report.json"
    csv_path = export_dir / "messages_per_day.csv"
    json_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "count"])
        for day, count in stats["messages_per_day"].items():
            writer.writerow([day, count])
    return json_path, csv_path


def plot_activity(stats: Dict[str, Any], export_dir: Path) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    dates = list(stats["messages_per_day"].keys())
    counts = list(stats["messages_per_day"].values())
    plt.figure(figsize=(8, 4))
    plt.plot(dates, counts, marker="o")
    plt.title("WhatsApp Activity")
    plt.xlabel("Date")
    plt.ylabel("Messages")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plot_path = export_dir / "activity.png"
    plt.savefig(plot_path)
    plt.close()
    return plot_path


def analyze_and_store(path: Path, entity_id: str, processor: EventProcessor, export_dir: Path) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    messages = parse_chat(content)
    stats = compute_stats(messages)
    export_reports(stats, export_dir)
    plot_activity(stats, export_dir)
    event = Event(
        entity_id=entity_id,
        event_type="whatsapp_export_analysis",
        payload=stats,
        source="wa_cli",
    )
    processor.emit(event)
    return stats
