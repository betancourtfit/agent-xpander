import os
import json
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException
import asyncio
from pydantic import BaseModel
from agno.agent import Agent

API_KEY = os.getenv("INTAKE_API_KEY", "").strip()

OUTPUT_SCHEMA_HINT = {
    "summary": "string",
    "assumptions": ["string"],
    "missing_questions": ["string"],
    "mvp_plan": [{"step": "string", "effort": "string"}],
    "risks": ["string"],
}

SYSTEM_RULES = f"""
You are an expert automation + AI consulting intake agent.
Return ONLY valid JSON. No markdown. No extra text.

The JSON MUST match this shape:
{json.dumps(OUTPUT_SCHEMA_HINT, ensure_ascii=False)}

Rules:
- Keep Spanish output.
- missing_questions: max 7 items.
- mvp_plan: 3 to 8 steps, each with step + effort (e.g. "1h", "4h", "1d").
- If info is missing, add it to missing_questions (do not invent).
""".strip()

def ensure_json(text: str) -> dict:
    if not text:
        return {"error": "empty_response"}
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        return {"error": "non_json_response", "raw": text[:2000]}

class InvokeReq(BaseModel):
    message: str

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

TIMEOUT_SECONDS = int(os.getenv("INVOKE_TIMEOUT", "60"))

agent = Agent(
    name="intake-agent",
    instructions=SYSTEM_RULES,
    model="openai:gpt-4o",   # ojo: provider:model
)
agent_lock = asyncio.Lock()

@app.post("/invoke")
async def invoke(req: InvokeReq, x_api_key: str | None = Header(default=None)):
    if API_KEY and (x_api_key or "").strip() != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        async with agent_lock:
            result = await asyncio.wait_for(agent.arun(input=req.message), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(
        status_code=504,
        detail={"error": "timeout", "after_seconds": TIMEOUT_SECONDS}
    )

    parsed = ensure_json(result.content)
    if "error" in parsed:
        raise HTTPException(status_code=502, detail=parsed)
    return parsed