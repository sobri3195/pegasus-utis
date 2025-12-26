from __future__ import annotations

import json
import re
from email import policy
from email.parser import BytesParser, Parser
from pathlib import Path
from typing import Any, Dict, List

from utis.core.events import EventProcessor
from utis.core.models import Event

URL_REGEX = re.compile(r"https?://[^\s>]+", re.IGNORECASE)
SUSPICIOUS_TLDS = {"zip", "xyz", "top", "work"}
ALLOWLIST_DOMAINS = {"example.com"}
DENYLIST_DOMAINS = {"secure-payments.bad"}


def _extract_domains(urls: List[str]) -> List[str]:
    domains = []
    for url in urls:
        match = re.match(r"https?://([^/]+)", url)
        if match:
            domains.append(match.group(1).lower())
    return domains


def _risk_score(urls: List[str]) -> Dict[str, Any]:
    score = 0
    domains = _extract_domains(urls)
    flags = []
    for domain in domains:
        tld = domain.split(".")[-1]
        if domain in DENYLIST_DOMAINS:
            score += 50
            flags.append(f"denylist:{domain}")
        if tld in SUSPICIOUS_TLDS:
            score += 10
            flags.append(f"suspicious_tld:{tld}")
        if domain in ALLOWLIST_DOMAINS:
            score -= 5
            flags.append(f"allowlist:{domain}")
    return {"score": max(score, 0), "flags": flags}


def _parse_headers(raw: str) -> Dict[str, Any]:
    message = Parser(policy=policy.default).parsestr(raw)
    received = message.get_all("Received", [])
    auth_results = message.get("Authentication-Results")
    return {
        "from": message.get("From"),
        "return_path": message.get("Return-Path"),
        "message_id": message.get("Message-ID"),
        "received_chain": received,
        "authentication_results": auth_results,
    }


def _detect_spoofing(headers: Dict[str, Any]) -> List[str]:
    findings = []
    from_header = headers.get("from") or ""
    return_path = headers.get("return_path") or ""
    if from_header and return_path and from_header not in return_path:
        findings.append("from_return_path_mismatch")
    if not headers.get("authentication_results"):
        findings.append("missing_authentication_results")
    return findings


def analyze_email(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() == ".eml":
        raw_bytes = path.read_bytes()
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
        raw_headers = message.as_string()
    else:
        raw_headers = path.read_text(encoding="utf-8")
    headers = _parse_headers(raw_headers)
    urls = URL_REGEX.findall(raw_headers)
    risk = _risk_score(urls)
    spoofing = _detect_spoofing(headers)
    return {
        "headers": headers,
        "urls": urls,
        "risk": risk,
        "spoofing_indicators": spoofing,
        "notes": "Header-based analysis only (no DNS lookup).",
    }


def analyze_and_store(path: Path, entity_id: str, processor: EventProcessor) -> Dict[str, Any]:
    report = analyze_email(path)
    event = Event(
        entity_id=entity_id,
        event_type="email_analysis",
        payload=report,
        source="email_cli",
    )
    processor.emit(event)
    return report


def save_report(report: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
