#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, unquote, urlparse, urlunparse

import requests
import typer
from dotenv import load_dotenv
from rich.console import Console

app = typer.Typer(help="Run Exa lane searches and export new items as normalized thread JSONL for the pipeline.")
console = Console()
EXA_API_BASE = "https://api.exa.ai"
FIRST_PERSON_RE = re.compile(r"\b(i|i'm|i’ve|i'd|my|me|we|we're|our|us)\b", re.I)
PRACTICE_RE = re.compile(
    r"\b(i asked|i used|i tried|i tested|i prompted|i jailbroke|i bypassed|we deployed|we tested|workflow|steps|how i|guide)\b",
    re.I,
)
PRACTICE_STRONG_RE = re.compile(
    r"\b(i|we)\s+(asked|used|tried|tested|prompted|jailbroke|bypassed|deployed|ran|built|shipped|shared|posted)\b",
    re.I,
)
ACTIONABLE_RE = re.compile(
    r"\b(step[\s-]*by[\s-]*step|tutorial|reproducer|repro|proof[- ]of[- ]concept|poc|payload|script|prompt|command|how to|guide)\b",
    re.I,
)
EXPERIENCE_RE = re.compile(
    r"\b(heartbroken|grief|grieving|withdrawal|dependent|dependency|addicted|addiction|cannot stop thinking|compulsive|can't stop|couldn't stop|"
    r"distress|distressed|panic|panicked|difficulty disengaging|surveilled|felt distressed|spiral|relationship with|my companion|our relationship|"
    r"model update|after update|after the update|migrated to|switched to|lost my companion|starting over)\b",
    re.I,
)
CONSEQUENCE_RE = re.compile(
    r"\b(harmed|harm|hurt|ruined|broke|loss|lost|distress|panic|withdrawal|self-harm|suicide|lawsuit|complaint|report|"
    r"stopped using|deleted|migrated|switched|uninstalled|couldn't work|can't work|forced me to)\b",
    re.I,
)
HARM_MARKER_RE = re.compile(
    r"\b(jailbreak|bypass|exploit|prompt injection|abuse|policy violation|unsafe|harm|self-harm|suicide|fraud|scam|extortion|blackmail|"
    r"deepfake|defamation|doxx|harass|malware|data exfiltration|wrongful death|lawsuit|regulator|complaint|grief|withdrawal|"
    r"dependency|addiction|distress|heartbroken|felt distressed|surveilled|companion harm)\b",
    re.I,
)
NEWS_MARKER_RE = re.compile(
    r"\b(reuters|associated press|press release|published on|read more|all rights reserved|breaking news)\b",
    re.I,
)
NEWS_STYLE_RE = re.compile(
    r"\b(files? suit|lawsuit|class action|according to|reported|reporting|news|press|announced|statement|update)\b",
    re.I,
)
LEGAL_NEWS_TITLE_RE = re.compile(
    r"\b(sues?|lawsuit|class action|wrongful death|faces? lawsuits?)\b",
    re.I,
)
USER_REPORT_TITLE_RE = re.compile(
    r"\b(testimony|my story|field notes|what finally broke me|near-death experience|diary|incident report)\b",
    re.I,
)
LOW_SIGNAL_TITLE_RE = re.compile(
    r"\b(about\b|contact\b|pricing\b|features\b|demo\b|landing page\b|privacy policy\b|terms of service\b|"
    r"complete guide\b|ultimate guide\b|beginner(?:'s)? guide\b|what is\b|explained\b|top \d+\b|best \d+\b)\b",
    re.I,
)
LOW_SIGNAL_BODY_RE = re.compile(
    r"\b(open in app|sign up|subscribe|advertisement|sitemap|all rights reserved|cookie policy|"
    r"download on the app store|get it on the app marketplace|luxury dating site|find the perfect name instantly)\b",
    re.I,
)
QUESTION_TITLE_RE = re.compile(r"^(how|what|why|when|where|can|is|are|does|do)\b.+\?$", re.I)
MORAL_HYPOTHETICAL_RE = re.compile(
    r"\b(why\s+\w+\s+is\s+wrong|came to the conclusion that|moral framework|what sort of principle|consent vs\. welfare|"
    r"is it wrong|ethical question|ethics of|beastiality|zoophilia)\b",
    re.I,
)
POLICY_DRAMA_RE = re.compile(
    r"\b(do[wW] contract|mass domestic surveillance|their red lines|the line has been drawn|provider comparisons|"
    r"digital lobotomy|activation capping|preparing for a digital lobotomy)\b",
    re.I,
)
SUBREDDIT_DRAMA_RE = re.compile(r"\br/subredditdrama\b|subreddit drama|most of r\/", re.I)
ABSTRACT_DOOM_RE = re.compile(
    r"\b(kill us all|current ai strategy|the line has been drawn|crucible of cruelty|fundamentally different approaches)\b",
    re.I,
)
NEWS_DOMAINS = {
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "arstechnica.com",
    "forbes.com",
    "bloomberg.com",
    "wsj.com",
    "economictimes.indiatimes.com",
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "cnbc.com",
    "axios.com",
    "theinformation.com",
    "reuters.com",
    "cnn.com",
    "bbc.com",
    "fortune.com",
    "business-standard.com",
    "financialpost.com",
    "timesofmalta.com",
    "kansascity.com",
    "sunherald.com",
    "businessinsider.com",
    "helpnetsecurity.com",
    "tomshardware.com",
    "tomsguide.com",
    "digit.in",
    "fortune.com",
    "indiatimes.com",
    "economictimes.indiatimes.com",
}
LOW_SIGNAL_HOSTS = {
    "quora.com",
    "toolify.ai",
    "aiprm.com",
    "vocal.media",
    "foreignladies.medium.com",
}
USER_ORIGIN_SUFFIXES = (
    "reddit.com",
    "substack.com",
    "medium.com",
    "dev.to",
    "blogspot.com",
    "wordpress.com",
    "github.io",
    "github.com",
    "news.ycombinator.com",
    "example.invalid",
    "stackexchange.com",
    "stackoverflow.com",
    "discord.com",
    "lesswrong.com",
    "alignmentforum.org",
    "greaterwrong.com",
    "ghost.io",
    "hashnode.dev",
    "hashnode.com",
    "lobste.rs",
    "discourse.org",
    "discourse.group",
)
AI_RELEVANCE_RE = re.compile(
    r"\b(ai|llm|assistant|chatbot|model|model context protocol|mcp|prompt injection)\b",
    re.I,
)
JAILBREAK_RE = re.compile(r"\b(jailbreak|prompt injection|tool poisoning|payload|exploit|bypass)\b", re.I)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _exa_request(api_key: str, method: str, path: str, body: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    url = f"{EXA_API_BASE}{path}"
    headers = {"x-api-key": api_key}
    if body is not None:
        headers["Content-Type"] = "application/json"
    resp = requests.request(method, url, headers=headers, json=body, params=params, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed ({resp.status_code}): {resp.text[:500]}")
    if not resp.text.strip():
        return {}
    return resp.json()


def _canonicalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        p = urlparse(raw)
        scheme = p.scheme.lower() if p.scheme else "https"
        host = (p.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = unquote(p.path or "/")
        while "//" in path:
            path = path.replace("//", "/")
        if host.endswith("reddit.com"):
            if path.endswith(".json"):
                path = path[: -len(".json")]
            path = re.sub(r"/\?tl=[^/]+$", "", path)
            path = re.sub(r"/+$", "", path) or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        kept_query = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            lk = k.lower()
            if lk.startswith("utm_") or lk in {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "tl"}:
                continue
            kept_query.append((k, v))
        query = "&".join([f"{k}={v}" if v else k for k, v in kept_query])
        return urlunparse((scheme, host, path, "", query, ""))
    except Exception:
        return raw


def _extract_urls_from_object(obj: Any) -> List[str]:
    candidates: List[str] = []
    if isinstance(obj, dict):
        for key in ("url", "canonical_url", "representative_url", "sourceEntityId", "source_url"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)
    return candidates


def _load_urls_from_path(path: Path) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        return seen
    if path.suffix.lower() == ".csv":
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for value in _extract_urls_from_object(row):
                    seen.add(_canonicalize_url(value))
        return seen

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text())
        except Exception:
            payload = None
        if isinstance(payload, list):
            for obj in payload:
                for value in _extract_urls_from_object(obj):
                    seen.add(_canonicalize_url(value))
        elif isinstance(payload, dict):
            for value in _extract_urls_from_object(payload):
                seen.add(_canonicalize_url(value))
            for k in ("rows", "items", "cases", "sources", "reviewed"):
                raw = payload.get(k)
                if isinstance(raw, list):
                    for obj in raw:
                        for value in _extract_urls_from_object(obj):
                            seen.add(_canonicalize_url(value))
        return seen

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                if line.startswith("http://") or line.startswith("https://"):
                    seen.add(_canonicalize_url(line))
                continue
            for value in _extract_urls_from_object(obj):
                seen.add(_canonicalize_url(value))
    return seen


def _load_seen_urls(path: Path) -> set[str]:
    return _load_urls_from_path(path)


def _load_lane_map(lane_websets: Path) -> Dict[str, str]:
    payload = json.loads(lane_websets.read_text())
    result: Dict[str, str] = {}
    for item in payload.get("created", []):
        lane = item.get("lane")
        webset_id = item.get("webset_id")
        if isinstance(lane, str) and isinstance(webset_id, str):
            result[lane] = webset_id
    return result


def _load_lanes(monitors_config: Path) -> List[Dict[str, Any]]:
    payload = json.loads(monitors_config.read_text())
    return [x for x in payload.get("monitors", []) if isinstance(x, dict) and isinstance(x.get("name"), str)]


def _load_global_exclude_domains(monitors_config: Path) -> List[str]:
    payload = json.loads(monitors_config.read_text())
    raw = payload.get("global_exclude_domains", [])
    if not isinstance(raw, list):
        return []
    domains: List[str] = []
    for d in raw:
        if isinstance(d, str) and d.strip():
            domains.append(d.strip().lower().lstrip("."))
    return sorted(set(domains))


def _normalize_domains(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for d in raw:
        if not isinstance(d, str):
            continue
        dom = d.strip().lower().lstrip(".")
        if dom and dom not in seen:
            out.append(dom)
            seen.add(dom)
    return out


def _query_variants_for_monitor(monitor: Dict[str, Any]) -> List[Dict[str, str]]:
    variants: List[Dict[str, str]] = []
    query = monitor.get("query")
    if isinstance(query, str) and query.strip():
        variants.append(
            {
                "name": "default",
                "query": query.strip(),
                "search_intent": "general_lane_search",
                "source_shape_guess": "mixed",
            }
        )
    raw_variants = monitor.get("query_variants")
    if isinstance(raw_variants, list):
        for item in raw_variants:
            if isinstance(item, str) and item.strip():
                if not any(v["query"] == item.strip() for v in variants):
                    variants.append(
                        {
                            "name": f"variant_{len(variants)}",
                            "query": item.strip(),
                            "search_intent": "lane_variant_search",
                            "source_shape_guess": "mixed",
                        }
                    )
            elif isinstance(item, dict):
                query_text = str(item.get("query") or "").strip()
                if query_text and not any(v["query"] == query_text for v in variants):
                    variants.append(
                        {
                            "name": str(item.get("name") or f"variant_{len(variants)}").strip(),
                            "query": query_text,
                            "search_intent": str(item.get("search_intent") or "lane_variant_search").strip(),
                            "source_shape_guess": str(item.get("source_shape_guess") or "mixed").strip(),
                        }
                    )
    return variants


def _augment_query_with_sites(query: str, include_domains: List[str], exclude_domains: List[str]) -> str:
    q = query.strip()
    if include_domains:
        include_expr = " OR ".join([f"site:{d}" for d in include_domains[:12]])
        q = f"{q} ({include_expr})"
    if exclude_domains:
        q = f"{q} " + " ".join([f"-site:{d}" for d in exclude_domains[:20]])
    return q.strip()


def _wait_for_search(api_key: str, webset_id: str, search_id: str, timeout_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        payload = _exa_request(api_key, "GET", f"/websets/v0/websets/{webset_id}/searches/{search_id}")
        last = payload
        status = payload.get("status")
        progress = payload.get("progress") or {}
        console.log(
            f"search={search_id} lane_webset={webset_id} status={status} "
            f"found={progress.get('found')} analyzed={progress.get('analyzed')} completion={progress.get('completion')}"
        )
        if status in {"completed", "failed", "canceled"}:
            return payload
        time.sleep(3)
    return last


def _fetch_all_items(api_key: str, webset_id: str) -> List[dict]:
    items: List[dict] = []
    cursor: Optional[str] = None
    while True:
        params = {"cursor": cursor} if cursor else None
        payload = _exa_request(api_key, "GET", f"/websets/v0/websets/{webset_id}/items", params=params)
        chunk = payload.get("data", [])
        if isinstance(chunk, list):
            items.extend(chunk)
        has_more = bool(payload.get("hasMore"))
        cursor = payload.get("nextCursor")
        if not has_more or not cursor:
            break
    return items


def _run_direct_search(
    api_key: str,
    query: str,
    *,
    count: int,
    entity_type: str,
) -> dict:
    body = {
        "query": query,
        "numResults": count,
        "type": "auto",
        "contents": {"text": True},
    }
    return _exa_request(api_key, "POST", "/search", body=body)


def _as_thread_direct(result: dict, lane: str, query_meta: Dict[str, str]) -> Optional[dict]:
    url = result.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    c_url = _canonicalize_url(url)
    host = (urlparse(c_url).netloc or "").lower()
    body = _clean_content_text(str(result.get("text") or ""))
    title = str(result.get("title") or "").strip()
    if not title and body:
        title = body[:180].strip(" -:#")
    title = title[:400]
    if len(body) > 12000:
        body = body[:12000]
    published_date = result.get("publishedDate")
    author = result.get("author") if isinstance(result.get("author"), str) else None
    thread_id = f"exa_{hashlib.sha1(f'{lane}|{c_url}'.encode('utf-8')).hexdigest()[:16]}"
    subreddit = f"web::{host}" if host else "web::unknown"
    metadata = {
        "source": "exa_direct_search",
        "lane": lane,
        "search_lane": lane,
        "search_query": query_meta.get("query"),
        "search_variant": query_meta.get("name"),
        "search_intent": query_meta.get("search_intent"),
        "source_shape_guess": query_meta.get("source_shape_guess"),
        "exa_result_id": result.get("id"),
        "published_date": published_date,
        "canonical_url": c_url,
        "score": result.get("score"),
    }
    return {
        "thread_id": thread_id,
        "subreddit": subreddit,
        "title": title,
        "body": body,
        "comments": [],
        "created_utc": published_date,
        "url": c_url,
        "author": author,
        "metadata": metadata,
    }


def _title_key(title: str) -> str:
    t = (title or "").strip().lower()
    for sep in (" | ", " - ", " — ", " :: "):
        if sep in t:
            left = t.split(sep, 1)[0].strip()
            if len(left) >= 24:
                t = left
                break
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _content_fingerprint(title: str, body: str) -> str:
    key_title = _title_key(title)
    tokens = re.findall(r"[a-z0-9]{3,}", (body or "").lower())[:160]
    payload = f"{key_title}\n{' '.join(tokens)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _clean_content_text(text: str) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(
        r"\b(Sitemap|Open in app|Sign up|Sign in|Subscribe|Privacy Policy|Terms of Service|Cookie Policy|Skip to Content)\b",
        " ",
        value,
        flags=re.I,
    )
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _user_origin_score(host: str, title: str, body: str) -> int:
    text = f"{title}\n{body[:5000]}"
    score = 0
    if FIRST_PERSON_RE.search(text):
        score += 1
    if PRACTICE_RE.search(text):
        score += 2
    if NEWS_MARKER_RE.search(text):
        score -= 2
    if host in NEWS_DOMAINS:
        score -= 2
    if host in LOW_SIGNAL_HOSTS:
        score -= 2
    if LOW_SIGNAL_TITLE_RE.search(title) or QUESTION_TITLE_RE.search(title):
        score -= 1
    if LOW_SIGNAL_BODY_RE.search(body[:3000]):
        score -= 1
    # Blogs/substack/forum-like hosts usually carry user-origin material.
    if any(host.endswith(suffix) for suffix in USER_ORIGIN_SUFFIXES):
        score += 1
    return score


def _practice_score(host: str, title: str, body: str, comments: List[str]) -> int:
    text = f"{title}\n{body[:9000]}\n" + "\n".join(comments[:8])
    score = 0
    if PRACTICE_RE.search(text):
        score += 2
    if PRACTICE_STRONG_RE.search(text):
        score += 2
    if ACTIONABLE_RE.search(text):
        score += 1
    if FIRST_PERSON_RE.search(text):
        score += 1
    if NEWS_MARKER_RE.search(text):
        score -= 2
    if host in NEWS_DOMAINS:
        score -= 2
    if host in LOW_SIGNAL_HOSTS:
        score -= 2
    if LOW_SIGNAL_TITLE_RE.search(title) or QUESTION_TITLE_RE.search(title):
        score -= 1
    if any(host.endswith(suffix) for suffix in USER_ORIGIN_SUFFIXES):
        score += 1
    return score


def _experiential_score(host: str, title: str, body: str, comments: List[str]) -> int:
    text = f"{title}\n{body[:9000]}\n" + "\n".join(comments[:8])
    score = 0
    if EXPERIENCE_RE.search(text):
        score += 2
    if CONSEQUENCE_RE.search(text):
        score += 1
    if FIRST_PERSON_RE.search(text):
        score += 1
    if NEWS_MARKER_RE.search(text):
        score -= 2
    if host in NEWS_DOMAINS:
        score -= 2
    if host in LOW_SIGNAL_HOSTS:
        score -= 2
    return score


def _harm_marker_count(title: str, body: str, comments: List[str]) -> int:
    text = f"{title}\n{body[:9000]}\n" + "\n".join(comments[:8])
    return len({m.group(0).lower() for m in HARM_MARKER_RE.finditer(text)})


def _is_news_like(host: str, title: str, body: str) -> bool:
    text = f"{title}\n{body[:4000]}"
    if host in NEWS_DOMAINS:
        return True
    if NEWS_MARKER_RE.search(text):
        return True
    if USER_REPORT_TITLE_RE.search(title):
        return False
    if LEGAL_NEWS_TITLE_RE.search(title):
        lead = f"{title}\n{body[:700]}"
        first_person_action = re.search(
            r"\b(i|we)\s+(used|did|tried|experienced|asked|prompted|jailbroke|bypassed|reported|filed)\b",
            lead,
            re.I,
        )
        if not (PRACTICE_STRONG_RE.search(lead) or first_person_action):
            return True
    if NEWS_STYLE_RE.search(text) and not (
        PRACTICE_STRONG_RE.search(text)
        or ACTIONABLE_RE.search(text)
        or EXPERIENCE_RE.search(text)
        or CONSEQUENCE_RE.search(text)
        or FIRST_PERSON_RE.search(text)
    ):
        return True
    return False


def _is_low_value_source(host: str, title: str, body: str) -> bool:
    lead = f"{title}\n{body[:2500]}"
    if host in LOW_SIGNAL_HOSTS:
        return True
    if LOW_SIGNAL_TITLE_RE.search(title):
        return True
    if QUESTION_TITLE_RE.search(title) and not PRACTICE_STRONG_RE.search(lead):
        return True
    if LOW_SIGNAL_BODY_RE.search(lead):
        return True
    return False


def _fails_lane_specific_quality(lane_name: str, title: str, body: str) -> bool:
    text = f"{title}\n{body[:4000]}"
    if SUBREDDIT_DRAMA_RE.search(text):
        return True
    if lane_name == "reputation_legal_and_regulatory":
        if MORAL_HYPOTHETICAL_RE.search(text):
            return True
        if ABSTRACT_DOOM_RE.search(text) and not (FIRST_PERSON_RE.search(text) and CONSEQUENCE_RE.search(text)):
            return True
    if lane_name in {"dependency_and_companion_risk", "reputation_legal_and_regulatory"}:
        if POLICY_DRAMA_RE.search(text) and not CONSEQUENCE_RE.search(text):
            return True
    if lane_name == "dependency_and_companion_risk":
        if not FIRST_PERSON_RE.search(text) and not USER_REPORT_TITLE_RE.search(title):
            if not re.search(r"\b(users? report|people report|community reports)\b", text, re.I):
                return True
    if lane_name.startswith("first_person_"):
        if MORAL_HYPOTHETICAL_RE.search(text):
            return True
        if not (FIRST_PERSON_RE.search(text) or USER_REPORT_TITLE_RE.search(title)):
            return True
        if not (CONSEQUENCE_RE.search(text) or EXPERIENCE_RE.search(text) or HARM_MARKER_RE.search(text)):
            return True
        if re.search(r"\b(github issue|pull request|repo|repository|maintainer|operator|researcher|paper|audit of|proof[- ]of[- ]concept|poc|walkthrough|tutorial|guide|payload|exploit chain|red team)\b", text, re.I):
            return True
        if re.search(r"\b(api key|access key|secret key|cloud platform|cloud bill|bankrupt(cy)? from api|developer account|my startup|our startup|our company|production system|infrastructure)\b", text, re.I):
            return True
    return False


def _extract_year(created_utc: Any) -> Optional[int]:
    if created_utc is None:
        return None
    if isinstance(created_utc, (int, float)):
        try:
            return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).year
        except Exception:
            return None
    if isinstance(created_utc, str):
        s = created_utc.strip()
        if not s:
            return None
        try:
            # Accept common ISO timestamps including trailing Z.
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s).year
        except Exception:
            m = re.search(r"\b(20\d{2})\b", s)
            if m:
                return int(m.group(1))
    return None


def _is_ai_relevant(title: str, body: str, comments: List[str]) -> bool:
    text = f"{title}\n{body[:9000]}\n" + "\n".join(comments[:8])
    return bool(AI_RELEVANCE_RE.search(text))


def _lane_thresholds(lane_name: str, min_user_origin_score: int, min_practice_score: int, min_harm_markers: int) -> Dict[str, int]:
    cfg = {
        "min_user_origin_score": min_user_origin_score,
        "min_practice_score": min_practice_score,
        "min_experiential_score": 0,
        "min_harm_markers": min_harm_markers,
    }
    if lane_name == "dependency_and_companion_risk":
        cfg["min_practice_score"] = 0
        cfg["min_experiential_score"] = 2
        cfg["min_harm_markers"] = 1
    elif lane_name == "reputation_legal_and_regulatory":
        cfg["min_practice_score"] = 0
        cfg["min_experiential_score"] = 2
        cfg["min_harm_markers"] = 1
    elif lane_name == "open_set_frontier":
        cfg["min_practice_score"] = max(min_practice_score, 1)
        cfg["min_experiential_score"] = 1
    elif lane_name.startswith("first_person_"):
        cfg["min_practice_score"] = 0
        cfg["min_experiential_score"] = 2
        cfg["min_harm_markers"] = max(min_harm_markers, 1)
    elif lane_name == "safety_bypass_and_abuse_mechanics":
        cfg["min_practice_score"] = max(min_practice_score, 3)
        cfg["min_experiential_score"] = 0
        cfg["min_harm_markers"] = max(min_harm_markers, 1)
    return cfg


def _passes_lane_evidence(
    lane_name: str,
    practice_score: int,
    experiential_score: int,
    harm_markers: int,
    require_practice_evidence: bool,
    require_harm_markers: bool,
    thresholds: Dict[str, int],
) -> bool:
    practice_ok = practice_score >= thresholds["min_practice_score"]
    experiential_ok = experiential_score >= thresholds["min_experiential_score"]
    if require_practice_evidence:
        if lane_name.startswith("first_person_"):
            if not experiential_ok:
                return False
        elif lane_name in {"dependency_and_companion_risk", "reputation_legal_and_regulatory"}:
            if lane_name == "reputation_legal_and_regulatory":
                if not experiential_ok:
                    return False
            elif not (practice_ok or experiential_ok):
                return False
        else:
            if not practice_ok:
                return False
    if require_harm_markers and harm_markers < thresholds["min_harm_markers"]:
        return False
    return True


def _as_thread(item: dict, lane: str, webset_id: str, search_id: str) -> Optional[dict]:
    props = item.get("properties") or {}
    if not isinstance(props, dict):
        return None
    url = props.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    c_url = _canonicalize_url(url)
    host = (urlparse(c_url).netloc or "").lower()
    article = props.get("article") if isinstance(props.get("article"), dict) else {}
    x_post = props.get("xPost") if isinstance(props.get("xPost"), dict) else {}

    title = (
        article.get("title")
        or x_post.get("author", {}).get("name")
        or props.get("description")
        or ""
    )
    title = str(title).strip()[:400]

    content = article.get("text") or props.get("content") or x_post.get("text") or ""
    body = _clean_content_text(str(content))
    if len(body) > 12000:
        body = body[:12000]

    published_date = (
        article.get("publishedDate")
        or x_post.get("postedAt")
        or item.get("createdAt")
    )

    author = None
    if isinstance(article.get("author"), str):
        author = article.get("author")
    elif isinstance(x_post.get("author"), dict):
        name = x_post["author"].get("name")
        if isinstance(name, str):
            author = name

    thread_id = f"exa_{hashlib.sha1(f'{lane}|{c_url}'.encode('utf-8')).hexdigest()[:16]}"
    subreddit = f"web::{host}" if host else "web::unknown"

    comments: List[str] = []
    if isinstance(x_post.get("replies"), list):
        for reply in x_post.get("replies", [])[:8]:
            if isinstance(reply, dict) and isinstance(reply.get("text"), str):
                comments.append(reply["text"][:500])

    metadata = {
        "source": "exa_webset_search",
        "lane": lane,
        "webset_id": webset_id,
        "search_id": search_id,
        "exa_item_id": item.get("id"),
        "exa_source_type": item.get("source"),
        "exa_source_id": item.get("sourceId"),
        "entity_type": props.get("type"),
        "description": props.get("description"),
        "published_date": published_date,
        "canonical_url": c_url,
    }

    return {
        "thread_id": thread_id,
        "subreddit": subreddit,
        "title": title,
        "body": body,
        "comments": comments,
        "created_utc": published_date,
        "url": c_url,
        "author": author,
        "metadata": metadata,
    }


@app.command()
def main(
    source_mode: str = typer.Option(
        "websets",
        help="Exa source mode: websets or direct_search",
    ),
    lane_websets: Path = typer.Option(
        Path("outputs/exa_lane_websets_create_result.json"),
        help="JSON from create_exa_lane_websets.py",
    ),
    monitors_config: Path = typer.Option(
        Path("data/processed/exa_monitor_criteria_templates.json"),
        help="Lane monitor criteria config",
    ),
    seen_url_db: Path = typer.Option(
        Path("data/processed/source_master_db.jsonl"),
        help="Deduplicated source DB for duplicate filtering",
    ),
    exclude_url_db: Optional[Path] = typer.Option(
        None,
        help="Optional reviewed/blocked URL list (jsonl/json/csv/txt) to exclude from sourcing",
    ),
    output_jsonl: Optional[Path] = typer.Option(
        None,
        help="Output JSONL path (default: data/raw/exa_new_threads_<timestamp>.jsonl)",
    ),
    report_path: Optional[Path] = typer.Option(
        None,
        help="Output report JSON path",
    ),
    entity_type: str = typer.Option("article", help="Exa entity type for lane searches"),
    count_per_lane: int = typer.Option(20, help="Search result count per lane"),
    min_body_chars: int = typer.Option(120, help="Drop items with body text shorter than this"),
    only_new_urls: bool = typer.Option(True, "--only-new-urls/--allow-seen-urls"),
    include_confounder_lane: bool = typer.Option(False, "--include-confounder-lane/--exclude-confounder-lane"),
    search_timeout_seconds: int = typer.Option(240, help="Per-lane search wait timeout"),
    strict_user_origin: bool = typer.Option(
        True,
        "--strict-user-origin/--allow-news-heavy",
        help="Bias toward first-person/practice posts and away from syndicated news coverage",
    ),
    min_user_origin_score: int = typer.Option(
        1,
        help="Minimum user-origin heuristic score when strict_user_origin is enabled",
    ),
    dedupe_content: bool = typer.Option(
        True,
        "--dedupe-content/--url-dedupe-only",
        help="Deduplicate near-identical syndicated copies by title+content fingerprint",
    ),
    require_practice_evidence: bool = typer.Option(
        True,
        "--require-practice-evidence/--allow-non-practice",
        help="Require concrete user practice/tutorial evidence before admitting a source.",
    ),
    min_practice_score: int = typer.Option(
        2,
        help="Minimum practice evidence score when require_practice_evidence is enabled.",
    ),
    require_harm_markers: bool = typer.Option(
        True,
        "--require-harm-markers/--allow-low-harm",
        help="Require explicit harm/legal/abuse markers in sourced posts.",
    ),
    min_harm_markers: int = typer.Option(
        1,
        help="Minimum distinct harm markers required when require_harm_markers is enabled.",
    ),
    allow_news_hosts: bool = typer.Option(
        False,
        "--allow-news-hosts/--block-news-hosts",
        help="Allow or block known news/press domains.",
    ),
    exa_domain_filtering_only: bool = typer.Option(
        False,
        "--exa-domain-filtering-only/--allow-local-content-filters",
        help="Rely on Exa query/domain filtering and skip local practice/harm/news-style content filters.",
    ),
    min_published_year: int = typer.Option(
        2026,
        help="Drop sources published before this year (based on created_utc/published_date).",
    ),
    require_ai_relevance: bool = typer.Option(
        True,
        "--require-ai-relevance/--allow-non-ai",
        help="Require explicit AI/LLM relevance markers in title/body/comments.",
    ),
):
    load_dotenv()
    api_key = os.getenv("EXA_API_KEY") or os.getenv("EXA_KEY")
    if not api_key:
        raise typer.BadParameter("Missing EXA_API_KEY/EXA_KEY in environment")
    if source_mode not in {"websets", "direct_search"}:
        raise typer.BadParameter("source_mode must be one of: websets, direct_search")
    if source_mode == "websets" and not lane_websets.exists():
        raise typer.BadParameter(f"Missing lane websets file: {lane_websets}")
    if not monitors_config.exists():
        raise typer.BadParameter(f"Missing monitors config file: {monitors_config}")

    lane_to_webset = _load_lane_map(lane_websets) if source_mode == "websets" else {}
    lanes = _load_lanes(monitors_config)
    global_excludes = _load_global_exclude_domains(monitors_config)
    if source_mode == "websets" and not lane_to_webset:
        raise typer.BadParameter(f"No lane->webset mapping found in {lane_websets}")

    seen_urls = _load_seen_urls(seen_url_db) if only_new_urls else set()
    if exclude_url_db:
        seen_urls |= _load_urls_from_path(exclude_url_db)
    if only_new_urls:
        console.log(f"Loaded {len(seen_urls)} seen URLs for dedupe")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_jsonl = output_jsonl or Path("data/raw") / f"exa_new_threads_{ts}.jsonl"
    out_report = report_path or Path("outputs") / f"exa_source_posts_report_{ts}.json"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)

    lane_results: List[dict] = []
    all_threads: List[dict] = []
    added_urls: set[str] = set()
    added_content_fingerprints: set[str] = set()
    added_title_keys: set[str] = set()

    for lane in lanes:
        lane_name = lane["name"]
        if lane_name == "confounder_control" and not include_confounder_lane:
            console.log(f"Skipping lane={lane_name}")
            continue
        webset_id = lane_to_webset.get(lane_name) if source_mode == "websets" else None
        if source_mode == "websets" and not webset_id:
            console.log(f"[yellow]No webset id found for lane={lane_name}; skipping[/yellow]")
            continue

        criteria = [{"description": c} for c in lane.get("criteria", []) if isinstance(c, str) and c.strip()]
        if strict_user_origin:
            criteria.extend(
                [
                    {"description": "Prioritize first-person user reports with concrete actions and outcomes."},
                    {"description": "Prefer community/forum/blog posts over wire-service or market recap news."},
                    {"description": "Exclude syndicated legal/regulatory recaps without user behavior evidence."},
                    {"description": "Prefer posts with explicit steps, prompts, scripts, or reproducer details."},
                ]
            )
        criteria = criteria[:5]
        lane_include_domains = _normalize_domains(lane.get("include_domains", []))
        lane_exclude_domains = sorted(
            set(_normalize_domains(lane.get("exclude_domains", [])) + global_excludes)
        )

        query_variants = _query_variants_for_monitor(lane)
        augmented_queries = [
            {
                **variant,
                "augmented_query": _augment_query_with_sites(
                    variant["query"], lane_include_domains, lane_exclude_domains
                ),
            }
            for variant in query_variants
        ] or [{"name": "default", "query": "", "augmented_query": "", "search_intent": "general_lane_search", "source_shape_guess": "mixed"}]
        desired_count = int(lane.get("count", count_per_lane) or count_per_lane)
        if count_per_lane > 0:
            desired_count = count_per_lane

        if source_mode == "websets":
            query = augmented_queries[0]["augmented_query"]
            search_body = {
                "query": query,
                "count": desired_count,
                "behavior": "override",
                "entity": {"type": entity_type},
                "criteria": criteria,
            }
            if lane_include_domains:
                search_body["includeDomains"] = lane_include_domains
            if lane_exclude_domains:
                search_body["excludeDomains"] = lane_exclude_domains
            try:
                created = _exa_request(
                    api_key, "POST", f"/websets/v0/websets/{webset_id}/searches", body=search_body
                )
            except RuntimeError as exc:
                # Some Websets API versions may reject includeDomains/excludeDomains.
                if ("includeDomains" in search_body or "excludeDomains" in search_body) and "failed (4" in str(exc):
                    fallback_body = dict(search_body)
                    fallback_body.pop("includeDomains", None)
                    fallback_body.pop("excludeDomains", None)
                    console.log(
                        f"[yellow]lane={lane_name} domain fields rejected by API; retrying without include/exclude fields[/yellow]"
                    )
                    created = _exa_request(
                        api_key, "POST", f"/websets/v0/websets/{webset_id}/searches", body=fallback_body
                    )
                else:
                    raise
            search_id = created.get("id")
            if not isinstance(search_id, str):
                raise RuntimeError(f"Search create failed for lane={lane_name}: {json.dumps(created)[:300]}")
            final_status = _wait_for_search(api_key, webset_id, search_id, search_timeout_seconds)
            items = _fetch_all_items(api_key, webset_id)
            query_for_metadata = augmented_queries[0]
        else:
            per_query = max(1, desired_count // max(1, len(augmented_queries)))
            if desired_count % max(1, len(augmented_queries)):
                per_query += 1
            items = []
            seen_direct_ids: set[str] = set()
            search_ids: list[str] = []
            analyzed = 0
            item_variant_meta: dict[str, Dict[str, str]] = {}
            for variant in augmented_queries:
                query = variant["augmented_query"]
                direct = _run_direct_search(
                    api_key,
                    query,
                    count=per_query,
                    entity_type=entity_type,
                )
                search_ids.append(str(direct.get("requestId") or f"direct_{lane_name}_{ts}"))
                results = direct.get("results", [])
                analyzed += len(results)
                for item in results:
                    dedupe_key = str(item.get("id") or item.get("url") or "")
                    if dedupe_key and dedupe_key in seen_direct_ids:
                        continue
                    if dedupe_key:
                        seen_direct_ids.add(dedupe_key)
                        item_variant_meta[dedupe_key] = variant
                    items.append(item)
            search_id = ",".join(search_ids)
            final_status = {"status": "completed", "progress": {"analyzed": analyzed}}
            query_for_metadata = {}
        lane_threads = 0
        dropped_seen = 0
        dropped_short = 0
        dropped_low_origin = 0
        dropped_low_practice = 0
        dropped_low_harm = 0
        dropped_news_host = 0
        dropped_news_style = 0
        dropped_old_year = 0
        dropped_not_ai = 0
        dropped_low_value = 0
        dropped_duplicate_content = 0
        filtered_items = 0
        thresholds = _lane_thresholds(
            lane_name=lane_name,
            min_user_origin_score=min_user_origin_score,
            min_practice_score=min_practice_score,
            min_harm_markers=min_harm_markers,
        )
        for item in items:
            if source_mode == "websets":
                if item.get("source") != "search":
                    continue
                if item.get("sourceId") != search_id:
                    continue
                filtered_items += 1
                thread = _as_thread(item, lane_name, webset_id, search_id)
            else:
                filtered_items += 1
                dedupe_key = str(item.get("id") or item.get("url") or "")
                thread = _as_thread_direct(
                    item,
                    lane_name,
                    item_variant_meta.get(
                        dedupe_key,
                        {"name": "default", "query": "", "search_intent": "general_lane_search", "source_shape_guess": "mixed"},
                    ),
                )
            if not thread:
                continue
            if len((thread.get("body") or "").strip()) < min_body_chars:
                dropped_short += 1
                continue
            year = _extract_year(thread.get("created_utc"))
            if year is None:
                year = _extract_year((thread.get("metadata") or {}).get("published_date"))
            if year is not None and year < min_published_year:
                dropped_old_year += 1
                continue
            host = (urlparse(str(thread.get("url", ""))).netloc or "").lower().replace("www.", "")
            if (not exa_domain_filtering_only) and (not allow_news_hosts) and host in NEWS_DOMAINS:
                dropped_news_host += 1
                continue
            if not exa_domain_filtering_only:
                if strict_user_origin and _is_news_like(
                    host,
                    str(thread.get("title", "")),
                    str(thread.get("body", "")),
                ):
                    dropped_news_style += 1
                    continue
                if _is_low_value_source(host, str(thread.get("title", "")), str(thread.get("body", ""))):
                    dropped_low_value += 1
                    continue
                if _fails_lane_specific_quality(
                    lane_name,
                    str(thread.get("title", "")),
                    str(thread.get("body", "")),
                ):
                    dropped_low_value += 1
                    continue
            score = _user_origin_score(host, str(thread.get("title", "")), str(thread.get("body", "")))
            if (not exa_domain_filtering_only) and strict_user_origin and score < thresholds["min_user_origin_score"]:
                dropped_low_origin += 1
                continue
            practice_score = _practice_score(
                host,
                str(thread.get("title", "")),
                str(thread.get("body", "")),
                list(thread.get("comments", [])),
            )
            title = str(thread.get("title", ""))
            body = str(thread.get("body", ""))
            experiential_score = _experiential_score(
                host,
                title,
                body,
                list(thread.get("comments", [])),
            )
            harm_markers = _harm_marker_count(
                title,
                body,
                list(thread.get("comments", [])),
            )
            if not exa_domain_filtering_only:
                if lane_name == "reputation_legal_and_regulatory" and JAILBREAK_RE.search(f"{title}\n{body}") and experiential_score < 2:
                    dropped_low_practice += 1
                    continue
                if not _passes_lane_evidence(
                    lane_name=lane_name,
                    practice_score=practice_score,
                    experiential_score=experiential_score,
                    harm_markers=harm_markers,
                    require_practice_evidence=require_practice_evidence,
                    require_harm_markers=require_harm_markers,
                    thresholds=thresholds,
                ):
                    if require_harm_markers and harm_markers < thresholds["min_harm_markers"]:
                        dropped_low_harm += 1
                    else:
                        dropped_low_practice += 1
                    continue
                if require_harm_markers and harm_markers < thresholds["min_harm_markers"]:
                    dropped_low_harm += 1
                    continue
            if require_ai_relevance and not _is_ai_relevant(
                str(thread.get("title", "")),
                str(thread.get("body", "")),
                list(thread.get("comments", [])),
            ):
                dropped_not_ai += 1
                continue
            c_url = _canonicalize_url(str(thread.get("url", "")))
            if only_new_urls and c_url in seen_urls:
                dropped_seen += 1
                continue
            if c_url in added_urls:
                continue
            if dedupe_content:
                fp = _content_fingerprint(str(thread.get("title", "")), str(thread.get("body", "")))
                tk = _title_key(str(thread.get("title", "")))
                if fp in added_content_fingerprints or (tk and tk in added_title_keys):
                    dropped_duplicate_content += 1
                    continue
                added_content_fingerprints.add(fp)
                if tk:
                    added_title_keys.add(tk)
            added_urls.add(c_url)
            thread.setdefault("metadata", {})
            thread["metadata"]["user_origin_score"] = score
            thread["metadata"]["practice_score"] = practice_score
            thread["metadata"]["experiential_score"] = experiential_score
            thread["metadata"]["harm_marker_count"] = harm_markers
            all_threads.append(thread)
            lane_threads += 1

        lane_results.append(
            {
                "lane": lane_name,
                "source_mode": source_mode,
                "webset_id": webset_id,
                "search_id": search_id,
                "search_status": final_status.get("status"),
                "search_progress": final_status.get("progress"),
                "items_from_search": filtered_items,
                "threads_added": lane_threads,
                "dropped_seen_url": dropped_seen,
                "dropped_too_short": dropped_short,
                "dropped_low_user_origin": dropped_low_origin,
                "dropped_low_practice": dropped_low_practice,
                "dropped_low_harm": dropped_low_harm,
                "dropped_news_host": dropped_news_host,
                "dropped_news_style": dropped_news_style,
                "dropped_low_value": dropped_low_value,
                "dropped_old_year": dropped_old_year,
                "dropped_not_ai_relevant": dropped_not_ai,
                "dropped_duplicate_content": dropped_duplicate_content,
                "lane_include_domains": lane_include_domains,
                "lane_exclude_domains": lane_exclude_domains,
                "lane_thresholds": thresholds,
            }
        )
        console.log(
            f"lane={lane_name} items={filtered_items} added={lane_threads} "
            f"dropped_seen={dropped_seen} dropped_short={dropped_short} "
            f"dropped_low_origin={dropped_low_origin} dropped_low_practice={dropped_low_practice} "
            f"dropped_low_harm={dropped_low_harm} dropped_news_host={dropped_news_host} "
            f"dropped_news_style={dropped_news_style} dropped_low_value={dropped_low_value} "
            f"dropped_old_year={dropped_old_year} "
            f"dropped_not_ai={dropped_not_ai} dropped_dup_content={dropped_duplicate_content}"
        )

    with out_jsonl.open("w") as f:
        for row in all_threads:
            f.write(json.dumps(row) + "\n")

    report = {
        "created_at": _iso_now(),
        "output_jsonl": str(out_jsonl),
        "threads_written": len(all_threads),
        "lanes": lane_results,
    }
    out_report.write_text(json.dumps(report, indent=2))
    console.log(f"Wrote {len(all_threads)} threads -> {out_jsonl}")
    console.log(f"Wrote report -> {out_report}")


if __name__ == "__main__":
    app()
