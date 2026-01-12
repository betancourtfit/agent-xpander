import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from intent_classifier import classify_intent_and_score
from agno.agent import Agent

# =====================
# Config
# =====================
API_KEY = os.getenv("INTAKE_API_KEY", "").strip()
TIMEOUT_SECONDS = int(os.getenv("INVOKE_TIMEOUT", "60"))

# =====================
# App
# =====================
app = FastAPI()


class InvokeReq(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"ok": True}


# =====================
# Local execution agent
# (solo para DEV / fallback)
# =====================
agent = Agent(
    name="intake-agent",
    instructions=os.getenv("LOCAL_AGENT_INSTRUCTIONS", "").strip() or None,
)
agent_lock = asyncio.Lock()


def _ensure_json_or_502(text: str) -> dict:
    if not text:
        raise HTTPException(status_code=502, detail="empty_response")

    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

    raise HTTPException(
        status_code=502,
        detail={"error": "non_json_response", "raw": text[:2000]},
    )


@app.post("/invoke")
async def invoke(
    req: InvokeReq,
    x_api_key: str | None = Header(default=None),
):
    # 1) Auth
    if API_KEY and (x_api_key or "").strip() != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Intent classification (determinístico)
    intent_pack = classify_intent_and_score(req.message)

    # 3) Ejecutar agente (local DEV mode)
    try:
        async with agent_lock:
            result = await asyncio.wait_for(
                agent.arun(input=req.message),
                timeout=TIMEOUT_SECONDS,
            )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"error": "timeout", "after_seconds": TIMEOUT_SECONDS},
        )

    # 4) JSON estricto
    parsed = _ensure_json_or_502(result.content)

    # 5) Response + headers
    resp = Response(
        content=json.dumps(parsed, ensure_ascii=False),
        media_type="application/json",
    )
    resp.headers["x-intent-id"] = str((intent_pack.get("intent") or {}).get("id", ""))
    resp.headers["x-intent-score"] = str(intent_pack.get("score", ""))
    resp.headers["x-intent-reasons"] = json.dumps(
        intent_pack.get("reasons", []),
        ensure_ascii=False,
    )

    return resp