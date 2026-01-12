# intent_classifier.py
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from intent_config import (
    INTENTS,
    SCORING_RULES,
    URGENCY_KEYWORDS,
    VAGUE_KEYWORDS,
)

BUDGET_RE = re.compile(r"\b(usd|us\$|\$)\s*\d+|\b\d+\s*(usd|dolares|dólares)\b", re.IGNORECASE)

STACK_KEYWORDS = [
    "airtable", "slack", "make", "zapier", "n8n", "hubspot", "pipedrive",
    "braze", "segment", "appsflyer", "ga4", "firebase", "supabase",
    "postgres", "bigquery", "s3", "lambda", "webhook", "api"
]

SCOPE_PATTERNS = [
    ("from_to", re.compile(r"\b(desde|from)\b.+\b(a|to)\b", re.IGNORECASE)),
    ("integrate", re.compile(r"\b(integrar|integración|integration|sync)\b", re.IGNORECASE)),
    ("automate", re.compile(r"\b(automatizar|automation|workflow)\b", re.IGNORECASE)),
]

@dataclass
class IntentResult:
    intent_id: str
    intent_label: str
    score: int
    reasons: List[str]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _contains_any(text: str, keywords: List[str]) -> List[str]:
    hits = []
    for k in keywords:
        if k and k.lower() in text:
            hits.append(k)
    return hits


def classify_intent_and_score(message: str) -> Dict:
    text = _norm(message)

    # -------- Intent (keyword overlap) --------
    best = ("other", "Otro / No clasificado", 0, [])
    for intent in INTENTS:
        kws = [k.lower() for k in intent.get("keywords", [])]
        hits = _contains_any(text, kws)
        if len(hits) > best[2]:
            best = (intent["id"], intent["label"], len(hits), hits)

    intent_id, intent_label, _, intent_hits = best

    # -------- Score (0..100) --------
    score = 0
    reasons: List[str] = []

    # Vague penalty first (pero no bloquea)
    vague_hits = _contains_any(text, VAGUE_KEYWORDS)
    if vague_hits:
        score += SCORING_RULES["is_vague_penalty"]
        reasons.append(f"vague_penalty({', '.join(vague_hits)})")

    # Budget
    if BUDGET_RE.search(text):
        score += SCORING_RULES["has_budget"]
        reasons.append("has_budget")

    # Urgency
    urg_hits = _contains_any(text, URGENCY_KEYWORDS)
    if urg_hits:
        score += SCORING_RULES["has_urgency"]
        reasons.append(f"has_urgency({', '.join(urg_hits)})")

    # Stack
    stack_hits = _contains_any(text, STACK_KEYWORDS)
    if stack_hits:
        score += SCORING_RULES["has_stack"]
        reasons.append(f"has_stack({', '.join(sorted(set(stack_hits)))})")

    # Scope
    scope_hit = False
    for name, rx in SCOPE_PATTERNS:
        if rx.search(text):
            scope_hit = True
            reasons.append(f"has_scope({name})")
            break
    if scope_hit:
        score += SCORING_RULES["has_scope"]

    # Intent signal boosts a little (si no es other)
    if intent_id != "other" and intent_hits:
        # boost suave por señales claras del intent
        score += min(10, 2 * len(intent_hits))
        reasons.append(f"intent_signal({', '.join(intent_hits)})")

    # clamp
    score = max(0, min(100, score))

    return {
        "intent": {"id": intent_id, "label": intent_label},
        "score": score,
        "reasons": reasons,
    }