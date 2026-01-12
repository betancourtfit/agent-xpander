from math import log
import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from intent_classifier import classify_intent_and_score

# =====================
# Config
# =====================
INTAKE_API_KEY = os.getenv("INTAKE_API_KEY", "").strip()
INVOKE_TIMEOUT = int(os.getenv("INVOKE_TIMEOUT", "60"))

XPANDER_API_KEY = os.getenv("XPANDER_API_KEY", "").strip()
XPANDER_AGENT_ID = os.getenv("XPANDER_AGENT_ID", "cd6c4b5c-8005-4c44-9e70-5831cefa608b").strip()
XPANDER_BASE_URL = (os.getenv("XPANDER_BASE_URL", "https://api.xpander.ai").strip().rstrip("/"))


# Endpoint típico de inbound (si tu doc difiere, cambiás SOLO esta constante)
XPANDER_INVOKE_PATH = os.getenv("XPANDER_INVOKE_PATH", f"/v1/agents/{XPANDER_AGENT_ID}/invoke").strip()

# =====================
# App
# =====================
app = FastAPI()


class InvokeReq(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"ok": True}


def _parse_json_or_error(text: str) -> dict:
    if not text:
        return {"error": "empty_response"}
    t = text.strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
        return {"error": "non_object_json", "raw": obj}
    except Exception:
        # intenta extraer bloque json
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                obj = json.loads(t[start:end + 1])
                if isinstance(obj, dict):
                    return obj
                return {"error": "non_object_json", "raw": obj}
            except Exception:
                pass
        return {"error": "non_json_response", "raw": t[:2000]}


async def _xpander_invoke(message: str) -> dict:
    if not XPANDER_API_KEY:
        raise HTTPException(status_code=500, detail={"error": "missing_xpander_api_key"})
    if not XPANDER_AGENT_ID:
        raise HTTPException(status_code=500, detail={"error": "missing_xpander_agent_id"})

    url = f"{XPANDER_BASE_URL}{XPANDER_INVOKE_PATH}"
    headers = {
        "x-api-key": XPANDER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"input": {"text": message}}

    timeout = httpx.Timeout(INVOKE_TIMEOUT, connect=10.0)
    # Muestra en consola los parámetros que se usarán en el fetch
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail={"error": "xpander_timeout", "after_seconds": INVOKE_TIMEOUT})
        except Exception as e:
            raise HTTPException(status_code=502, detail={"error": "xpander_network_error", "type": type(e).__name__, "message": str(e)[:300]})

    # Xpander a veces devuelve texto/json; normalizamos
    body_text = r.text or ""
    data = _parse_json_or_error(body_text)

    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "xpander_bad_status",
                "status_code": r.status_code,
                "response": data,
            },
        )

    # si el body no es json, también es 502
    if data.get("error"):
        raise HTTPException(status_code=502, detail={"error": "xpander_non_json", "response": data})

    return data

import re
from fastapi import HTTPException

_REQUIRED_KEYS = {"summary", "assumptions", "missing_questions", "mvp_plan", "risks"}
_EFFORT_RE = re.compile(r"^\d+(m|h|d)$")  # 15m, 1h, 2d


def _extract_agent_result(envelope: dict) -> dict:
    """
    Xpander suele devolver un execution envelope con un campo `result`
    que a veces viene como string JSON escapado.
    Acá devolvemos SOLO el JSON final del agente (dict).
    """
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=502, detail={"error": "xpander_invalid_envelope"})

    if "result" not in envelope:
        # Algunos endpoints podrían devolver directamente el resultado; soportamos eso best-effort
        if _ALLOWED_KEYS.issubset(set(envelope.keys())):
            return envelope
        raise HTTPException(status_code=502, detail={"error": "xpander_missing_result", "response": envelope})

    raw = envelope.get("result")

    # `result` puede venir como dict o como string JSON
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
            raise HTTPException(status_code=502, detail={"error": "xpander_result_not_object", "raw": obj})
        except Exception:
            raise HTTPException(
                status_code=502,
                detail={"error": "xpander_result_not_json", "raw": (raw or "")[:2000]},
            )

    raise HTTPException(status_code=502, detail={"error": "xpander_result_bad_type", "type": str(type(raw))})

def _normalize_contract(obj: dict) -> dict:
    """
    No estricto:
    - Permite keys extra (las ignora).
    - Si faltan keys, las completa con defaults.
    - Si tipos vienen mal, intenta convertir; si no, default.
    - Nunca levanta 502 por contrato.
    """

    if not isinstance(obj, dict):
        return {
            "summary": "",
            "assumptions": [],
            "missing_questions": [],
            "mvp_plan": [],
            "risks": [],
        }

    def _as_str(x):
        return x.strip() if isinstance(x, str) else str(x) if x is not None else ""

    def _as_list_str(x):
        if isinstance(x, list):
            return [_as_str(i) for i in x if _as_str(i)]
        if isinstance(x, str) and x.strip():
            return [x.strip()]
        return []

    def _as_mvp(x):
        if not isinstance(x, list):
            return []
        out = []
        for it in x:
            if isinstance(it, dict):
                step = _as_str(it.get("step"))
                effort = _as_str(it.get("effort"))
                if step:
                    out.append({"step": step, "effort": effort or "?"})
            elif isinstance(it, str) and it.strip():
                out.append({"step": it.strip(), "effort": "?"})
        return out

    normalized = {
        "summary": _as_str(obj.get("summary")),
        "assumptions": _as_list_str(obj.get("assumptions")),
        "missing_questions": _as_list_str(obj.get("missing_questions")),
        "mvp_plan": _as_mvp(obj.get("mvp_plan")),
        "risks": _as_list_str(obj.get("risks")),
    }

    # límites suaves (no estrictos)
    if len(normalized["missing_questions"]) > 7:
        normalized["missing_questions"] = normalized["missing_questions"][:7]

    if len(normalized["mvp_plan"]) > 8:
        normalized["mvp_plan"] = normalized["mvp_plan"][:8]

    return normalized

@app.post("/invoke")
async def invoke(req: InvokeReq, x_api_key: str | None = Header(default=None)):
    if INTAKE_API_KEY and (x_api_key or "").strip() != INTAKE_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_msg = (req.message or "").strip()

    # intent headers (local, determinístico)
    try:
        intent_pack = classify_intent_and_score(user_msg)
    except Exception as e:
        intent_pack = {
            "intent": {"id": "", "label": ""},
            "score": 0,
            "reasons": [f"classifier_error:{type(e).__name__}"],
        }

    # 1) Llamar a Xpander (tu función actual)
    envelope = await _xpander_invoke(user_msg)

    # 2) Extraer JSON final del agente
    result_obj = _extract_agent_result(envelope)

    # 3) Validar contract estricto
    agent_obj = _extract_agent_result(envelope)
    result_obj = _normalize_contract(agent_obj)

    resp = Response(
        content=json.dumps(result_obj, ensure_ascii=False),
        media_type="application/json",
    )
    return resp