import os
import json
from dotenv import load_dotenv
load_dotenv()

from xpander_sdk import Task, on_task, Backend, Tokens
from agno.agent import Agent

API_KEY = os.getenv("INTAKE_API_KEY", "").strip()

def _cfg_to_dict(cfg):
    if cfg is None:
        return {}
    if isinstance(cfg, dict):
        return cfg
    if hasattr(cfg, "model_dump"):
        try:
            return cfg.model_dump()
        except Exception:
            pass
    if hasattr(cfg, "dict"):
        try:
            return cfg.dict()
        except Exception:
            pass
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

    if not headers:
        return

    provided = (headers.get("x-api-key") or headers.get("X-API-KEY") or "").strip()
    if provided != API_KEY:
        raise PermissionError("Unauthorized: missing/invalid x-api-key")

def _ensure_json(text: str) -> str:
    if not text:
        return json.dumps({"error": "empty_response"}, ensure_ascii=False)

    text = text.strip()

    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass

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
    _require_api_key(task)

    backend = Backend(configuration=task.configuration)

    agno_args = await backend.aget_args(task=task)
    agno_agent = Agent(**agno_args)

    result = await agno_agent.arun(
        input=task.to_message(),
        files=task.get_files(),
        images=task.get_images()
    )

    task.result = _ensure_json(result.content)

    task.tokens = Tokens(
        prompt_tokens=getattr(result.metrics, "input_tokens", 0),
        completion_tokens=getattr(result.metrics, "output_tokens", 0),
    )
    task.used_tools = [tool.tool_name for tool in (result.tools or [])]

    return task