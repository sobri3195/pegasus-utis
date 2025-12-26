"""WhatsApp export chat (.txt) parser and analytics."""

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

try:
    from dateutil import parser as dtparser
    HAS_DATEUTIL = True
except ImportError:  # pragma: no cover
    dtparser = None
    HAS_DATEUTIL = False


LINE_PATTERNS = [
    # 12/31/20, 10:30 PM - Name: message
    re.compile(r"^(?P<dt>\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*-\s*(?P<rest>.*)$"),
    # 31/12/2020 22:30 - Name: message
    re.compile(r"^(?P<dt>\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2})\s*-\s*(?P<rest>.*)$"),
    # 31.12.2020, 22:30 - Name: message
    re.compile(r"^(?P<dt>\d{1,2}\.\d{1,2}\.\d{2,4},\s*\d{1,2}:\d{2})\s*-\s*(?P<rest>.*)$"),
]

STOPWORDS = {
    "the", "and", "to", "a", "of", "in", "is", "it", "i", "you", "for", "on", "this", "that",
    "dan", "yang", "di", "ke", "dari", "aku", "kamu", "gue", "lu", "nya", "aja", "ya", "ga", "gak",
}


@dataclass
class WhatsAppMessage:
    timestamp: datetime
    sender: str
    text: str


@dataclass
class WhatsAppAnalysisResult:
    input_path: str
    parsed_messages: int
    participants: List[str]
    messages_per_day: Dict[str, int]
    active_hours: Dict[int, int]
    top_words: List[Tuple[str, int]]
    response_time_seconds_avg: Optional[float]
    anomalies: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_path": self.input_path,
            "parsed_messages": self.parsed_messages,
            "participants": self.participants,
            "messages_per_day": self.messages_per_day,
            "active_hours": {str(k): v for k, v in self.active_hours.items()},
            "top_words": [{"word": w, "count": c} for w, c in self.top_words],
            "response_time_seconds_avg": self.response_time_seconds_avg,
            "anomalies": self.anomalies,
        }


def _parse_dt_fallback(dt_str: str, dayfirst: bool) -> Optional[datetime]:
    s = dt_str.strip()
    s = re.sub(r"\s+", " ", s)

    has_ampm = bool(re.search(r"\b[AP]M\b", s, re.IGNORECASE))

    # Determine year width
    year_match = re.search(r"(\d{2,4})(?:,|\s|$)", s)
    year_len = 4
    if year_match:
        year_len = len(year_match.group(1))

    candidates: List[str] = []

    # Slash formats
    if "/" in s:
        if "," in s and has_ampm:
            # 12/31/20, 10:30 PM
            if dayfirst:
                candidates += [
                    f"%d/%m/%y, %I:%M %p" if year_len == 2 else "%d/%m/%Y, %I:%M %p",
                ]
            else:
                candidates += [
                    f"%m/%d/%y, %I:%M %p" if year_len == 2 else "%m/%d/%Y, %I:%M %p",
                ]
        elif "," in s and not has_ampm:
            # 12/31/20, 22:30
            if dayfirst:
                candidates += [
                    f"%d/%m/%y, %H:%M" if year_len == 2 else "%d/%m/%Y, %H:%M",
                ]
            else:
                candidates += [
                    f"%m/%d/%y, %H:%M" if year_len == 2 else "%m/%d/%Y, %H:%M",
                ]
        else:
            # 31/12/2020 22:30
            if dayfirst:
                candidates += [
                    f"%d/%m/%y %H:%M" if year_len == 2 else "%d/%m/%Y %H:%M",
                ]
            else:
                candidates += [
                    f"%m/%d/%y %H:%M" if year_len == 2 else "%m/%d/%Y %H:%M",
                ]

    # Dot formats
    if "." in s and "," in s:
        # 31.12.2020, 22:30
        candidates += [
            f"%d.%m.%y, %H:%M" if year_len == 2 else "%d.%m.%Y, %H:%M",
        ]

    for fmt in candidates:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    return None


class WhatsAppAnalyzer:
    def parse(self, path: str) -> List[WhatsAppMessage]:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()

        msgs: List[WhatsAppMessage] = []
        current: Optional[WhatsAppMessage] = None

        dayfirst_guess = None

        for line in lines:
            m = None
            for pat in LINE_PATTERNS:
                m = pat.match(line)
                if m:
                    break

            if m:
                dt_str = m.group("dt")
                rest = m.group("rest")

                if dayfirst_guess is None:
                    # Try to infer dayfirst by inspecting first date token
                    nums = re.findall(r"\d+", dt_str)
                    if len(nums) >= 2:
                        a, b = int(nums[0]), int(nums[1])
                        # if first number > 12, it's likely dayfirst
                        dayfirst_guess = a > 12
                    else:
                        dayfirst_guess = True

                if HAS_DATEUTIL:
                    try:
                        ts = dtparser.parse(dt_str, dayfirst=bool(dayfirst_guess))
                    except Exception:
                        continue
                else:
                    ts = _parse_dt_fallback(dt_str, bool(dayfirst_guess))
                    if ts is None:
                        continue

                sender = ""
                text = rest
                if ": " in rest:
                    sender, text = rest.split(": ", 1)
                else:
                    sender = "system"

                current = WhatsAppMessage(timestamp=ts, sender=sender.strip(), text=text)
                msgs.append(current)
            else:
                # Continuation line
                if current is not None:
                    current.text += "\n" + line

        return msgs

    def analyze(self, path: str) -> WhatsAppAnalysisResult:
        msgs = self.parse(path)

        participants = sorted({m.sender for m in msgs if m.sender != "system"})

        per_day: Dict[str, int] = {}
        hours: Dict[int, int] = {h: 0 for h in range(24)}

        word_counts: Dict[str, int] = {}

        # response time (simple): average time delta when sender changes
        response_deltas = []
        for i in range(1, len(msgs)):
            prev, cur = msgs[i - 1], msgs[i]
            if prev.sender != cur.sender and prev.sender != "system" and cur.sender != "system":
                delta = (cur.timestamp - prev.timestamp).total_seconds()
                if 0 < delta < 24 * 3600:
                    response_deltas.append(delta)

        for m in msgs:
            day = m.timestamp.date().isoformat()
            per_day[day] = per_day.get(day, 0) + 1
            hours[m.timestamp.hour] = hours.get(m.timestamp.hour, 0) + 1

            for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+", m.text.lower()):
                if len(w) < 3:
                    continue
                if w in STOPWORDS:
                    continue
                word_counts[w] = word_counts.get(w, 0) + 1

        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:20]

        response_avg = mean(response_deltas) if response_deltas else None

        anomalies = self._detect_anomalies(per_day)

        return WhatsAppAnalysisResult(
            input_path=str(path),
            parsed_messages=len(msgs),
            participants=participants,
            messages_per_day=per_day,
            active_hours=hours,
            top_words=top_words,
            response_time_seconds_avg=response_avg,
            anomalies=anomalies,
        )

    def _detect_anomalies(self, per_day: Dict[str, int]) -> List[Dict[str, Any]]:
        if not per_day:
            return []

        counts = list(per_day.values())
        avg = mean(counts)
        # very small heuristic: spike if > 3x average and > 20 msgs
        anomalies = []
        for day, cnt in per_day.items():
            if cnt > max(20, 3 * avg):
                anomalies.append({"day": day, "count": cnt, "reason": "activity_spike"})
        return anomalies

    def export(self, result: WhatsAppAnalysisResult, out_dir: str) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        (out / "report.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

        # CSV exports
        with (out / "messages_per_day.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["day", "messages"])
            for day, cnt in sorted(result.messages_per_day.items()):
                w.writerow([day, cnt])

        with (out / "active_hours.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["hour", "messages"])
            for hour in range(24):
                w.writerow([hour, result.active_hours.get(hour, 0)])

        # Plot (optional dependency matplotlib)
        try:
            import matplotlib.pyplot as plt

            days = sorted(result.messages_per_day.keys())
            vals = [result.messages_per_day[d] for d in days]
            plt.figure(figsize=(10, 4))
            plt.plot(days, vals)
            plt.xticks(rotation=45, ha="right")
            plt.title("Messages per day")
            plt.tight_layout()
            plt.savefig(out / "messages_per_day.png")
            plt.close()

            plt.figure(figsize=(8, 4))
            hrs = list(range(24))
            hvals = [result.active_hours.get(h, 0) for h in hrs]
            plt.bar(hrs, hvals)
            plt.title("Active hours")
            plt.xlabel("Hour")
            plt.ylabel("Messages")
            plt.tight_layout()
            plt.savefig(out / "active_hours.png")
            plt.close()
        except Exception:
            # If matplotlib isn't available, skip plotting.
            pass
