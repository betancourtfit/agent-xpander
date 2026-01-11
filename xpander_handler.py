import os
import json
from dotenv import load_dotenv
load_dotenv()

from xpander_sdk import Task, on_task, Backend, Tokens
from agno.agent import Agent

# ============
# Config
# ============
API_KEY = os.getenv("INTAKE_API_KEY", "").strip()

# Respuesta JSON estricta (contract)
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
"""

def _cfg_to_dict(cfg):
    if cfg is None:
        return {}
    if isinstance(cfg, dict):
        return cfg

    # pydantic v2
    if hasattr(cfg, "model_dump"):
        try:
            return cfg.model_dump()
        except Exception:
            pass

    # pydantic v1
    if hasattr(cfg, "dict"):
        try:
            return cfg.dict()
        except Exception:
            pass

    # generic
    if hasattr(cfg, "to_dict"):
        try:
            return cfg.to_dict()
        except Exception:
            pass

    try:
        return vars(cfg) or {}
    except Exception:
        return {}

def _require_api_key(task: Task):
    # Si no configuraste API key, no bloqueamos (solo para dev)
    if not API_KEY:
        return

    cfg = _cfg_to_dict(task.configuration)

    headers = {}
    if isinstance(cfg.get("headers"), dict):
        headers = cfg["headers"]
    elif isinstance(cfg.get("request"), dict) and isinstance(cfg["request"].get("headers"), dict):
        headers = cfg["request"]["headers"]
    elif isinstance(cfg.get("metadata"), dict) and isinstance(cfg["metadata"].get("headers"), dict):
        headers = cfg["metadata"]["headers"]

    # En CLI invoke normalmente NO hay headers → no bloquear
    if not headers:
        return

    provided = (headers.get("x-api-key") or headers.get("X-API-KEY") or "").strip()
    if provided != API_KEY:
        raise PermissionError("Unauthorized: missing/invalid x-api-key")

def _ensure_json(text: str) -> str:
    """
    Best-effort: if model returns extra text, try to extract the first JSON object.
    If it fails, return a minimal error JSON (still valid JSON).
    """
    if not text:
        return json.dumps({"error": "empty_response"}, ensure_ascii=False)

    text = text.strip()

    # Fast path: valid JSON already
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass

    # Try to extract JSON block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            obj = json.loads(candidate)
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass

    return json.dumps({"error": "non_json_response", "raw": text[:2000]}, ensure_ascii=False)


@on_task
async def my_agent_handler(task: Task):
    # Security gate (minimal)
    _require_api_key(task)

    # Get xpander agent details
    backend = Backend(configuration=task.configuration)

    # Create Agno agent instance (provided by xpander)
    agno_args = await backend.aget_args(task=task)
    agno_agent = Agent(**agno_args)

    # Build input (we force system rules + user message)
    user_message = task.to_message()
    composed_input = f"{SYSTEM_RULES}\n\nUSER_INPUT:\n{user_message}"

    # Run the agent
    result = await agno_agent.arun(
        input=composed_input,
        files=task.get_files(),
        images=task.get_images()
    )

    # Enforce JSON output
    task.result = _ensure_json(result.content)

    # report execution metrics
    task.tokens = Tokens(
        prompt_tokens=getattr(result.metrics, "input_tokens", 0),
        completion_tokens=getattr(result.metrics, "output_tokens", 0),
    )
    task.used_tools = [tool.tool_name for tool in (result.tools or [])]

    return task