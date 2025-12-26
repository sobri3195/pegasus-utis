"""Analyze email headers and content for security/deliverability signals.

Note: This analyzer only evaluates what is present in the message (headers/body).
It does NOT perform DNS validation for SPF/DKIM/DMARC.
"""

import json
import os
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser, Parser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://[^\s<>"]+", re.IGNORECASE)

SUSPICIOUS_TLDS = {"zip", "mov", "top", "xyz", "click", "icu", "work", "support"}


def _read_list(path: Path) -> List[str]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(line.lower())
    return items


def _domain_from_addr(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"@([A-Za-z0-9.-]+)", value)
    return (m.group(1) if m else "").lower()


def _safe_str(s: Any) -> str:
    return "" if s is None else str(s)


@dataclass
class EmailAnalysisResult:
    input_path: str
    headers: Dict[str, Any]
    received_chain: List[str]
    urls: List[str]
    spoofing_indicators: List[str]
    auth_results: Dict[str, str]
    url_risk: Dict[str, Any]
    overall_risk_score: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_path": self.input_path,
            "headers": self.headers,
            "received_chain": self.received_chain,
            "urls": self.urls,
            "spoofing_indicators": self.spoofing_indicators,
            "auth_results": self.auth_results,
            "url_risk": self.url_risk,
            "overall_risk_score": self.overall_risk_score,
        }


class EmailAnalyzer:
    def __init__(self, allowlist_path: Optional[str] = None, denylist_path: Optional[str] = None):
        base = Path(__file__).parent / "lists"
        self.allowlist = set(_read_list(Path(allowlist_path) if allowlist_path else base / "allow.txt"))
        self.denylist = set(_read_list(Path(denylist_path) if denylist_path else base / "deny.txt"))

    def load_message(self, path: str):
        p = Path(path)
        data = p.read_bytes()
        try:
            return BytesParser(policy=policy.default).parsebytes(data)
        except Exception:
            # fallback for raw headers-only text
            return Parser(policy=policy.default).parsestr(p.read_text(encoding="utf-8", errors="replace"))

    def analyze(self, path: str) -> EmailAnalysisResult:
        msg = self.load_message(path)

        headers = {
            "From": _safe_str(msg.get("From")),
            "Return-Path": _safe_str(msg.get("Return-Path")),
            "Message-ID": _safe_str(msg.get("Message-ID")),
            "Subject": _safe_str(msg.get("Subject")),
            "Date": _safe_str(msg.get("Date")),
            "Authentication-Results": _safe_str(msg.get("Authentication-Results")),
        }

        received = msg.get_all("Received") or []
        received_chain = [str(r) for r in received]

        auth_results = self._parse_auth_results(headers.get("Authentication-Results", ""))

        spoofing_indicators = self._detect_spoofing(headers, auth_results)

        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    try:
                        body_text += part.get_content() + "\n"
                    except Exception:
                        pass
        else:
            try:
                body_text = msg.get_content() or ""
            except Exception:
                body_text = ""

        urls = list({u.rstrip(").,]>") for u in URL_RE.findall(body_text)})
        url_risk = self._score_urls(urls)

        score = 0
        score += min(50, 10 * len(spoofing_indicators))
        score += url_risk.get("risk_score", 0)
        if auth_results.get("spf") in ("fail", "softfail"):
            score += 15
        if auth_results.get("dkim") == "fail":
            score += 15
        if auth_results.get("dmarc") == "fail":
            score += 20
        score = max(0, min(100, score))

        return EmailAnalysisResult(
            input_path=str(path),
            headers=headers,
            received_chain=received_chain,
            urls=urls,
            spoofing_indicators=spoofing_indicators,
            auth_results=auth_results,
            url_risk=url_risk,
            overall_risk_score=score,
        )

    def _parse_auth_results(self, header_value: str) -> Dict[str, str]:
        # Extremely lightweight parsing.
        # Example: spf=pass smtp.mailfrom=...; dkim=pass header.d=...; dmarc=pass ...
        res: Dict[str, str] = {}
        if not header_value:
            return res
        for key in ("spf", "dkim", "dmarc"):
            m = re.search(rf"\b{key}=([a-zA-Z0-9_-]+)", header_value)
            if m:
                res[key] = m.group(1).lower()
        return res

    def _detect_spoofing(self, headers: Dict[str, Any], auth_results: Dict[str, str]) -> List[str]:
        findings: List[str] = []

        from_dom = _domain_from_addr(headers.get("From", ""))
        rp_dom = _domain_from_addr(headers.get("Return-Path", ""))
        mid_dom = _domain_from_addr(headers.get("Message-ID", ""))

        if from_dom and rp_dom and from_dom != rp_dom:
            findings.append("From domain differs from Return-Path domain")
        if from_dom and mid_dom and from_dom != mid_dom:
            findings.append("From domain differs from Message-ID domain")

        if auth_results.get("spf") in ("fail", "softfail"):
            findings.append(f"Authentication-Results indicates SPF {auth_results.get('spf')}")
        if auth_results.get("dkim") == "fail":
            findings.append("Authentication-Results indicates DKIM fail")
        if auth_results.get("dmarc") == "fail":
            findings.append("Authentication-Results indicates DMARC fail")

        if not headers.get("Message-ID"):
            findings.append("Missing Message-ID header")

        return findings

    def _score_urls(self, urls: List[str]) -> Dict[str, Any]:
        details = []
        score = 0
        for u in urls:
            try:
                parsed = urlparse(u)
                host = (parsed.hostname or "").lower()
            except Exception:
                host = ""

            url_score = 0
            url_findings = []

            if not host:
                url_score += 10
                url_findings.append("Unparseable host")
            else:
                if host in self.denylist or any(host.endswith("." + d) for d in self.denylist):
                    url_score += 40
                    url_findings.append("Domain is in local denylist")
                if host in self.allowlist or any(host.endswith("." + a) for a in self.allowlist):
                    url_score -= 10
                    url_findings.append("Domain is in local allowlist")

                if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
                    url_score += 25
                    url_findings.append("URL uses raw IPv4 address")

                if host.startswith("xn--"):
                    url_score += 15
                    url_findings.append("Punycode domain")

                parts = host.split(".")
                if parts:
                    tld = parts[-1]
                    if tld in SUSPICIOUS_TLDS:
                        url_score += 10
                        url_findings.append(f"Suspicious TLD: {tld}")

            url_score = max(0, min(60, url_score))
            score = max(score, url_score)  # take worst URL as overall URL risk
            details.append({"url": u, "host": host, "score": url_score, "findings": url_findings})

        return {"risk_score": score, "details": details}
