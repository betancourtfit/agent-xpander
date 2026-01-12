from pathlib import Path

content = """# Intake Agent – Xpander + Local Compute

## Descripción
Este proyecto implementa un **AI Intake Agent** para consultas de automatización y tecnología, combinando:

- **Cómputo en tu propio servidor** (FastAPI + Docker).
- **Configuración dinámica desde Xpander UI** (sin redeploy).
- **Clasificación determinística de intención y scoring** previa al LLM.
- **Contrato de salida JSON estable**, tolerante a variaciones del modelo.

El objetivo es recibir mensajes vía HTTP, clasificarlos, delegar el razonamiento al agente configurado en Xpander y devolver una respuesta limpia y usable por sistemas downstream (CRM, Slack, Notion, etc.).

---

## Arquitectura de alto nivel

```
Cliente HTTP
   |
   v
FastAPI (app.py)
   |
   |-- intent_classifier (determinístico)
   |
   |-- llamada HTTP -> Xpander API
   |        |
   |        v
   |   Agente configurado en Xpander UI
   |
   v
Normalización + validación JSON
   |
   v
Respuesta HTTP + headers de intent
```

---

## Componentes principales

### 1. `app.py`
Responsable de:
- Exponer la API HTTP (`/invoke`, `/health`).
- Autenticación por API Key.
- Clasificación de intención y scoring.
- Invocar al agente de Xpander vía API.
- Extraer y normalizar el resultado del agente.
- Devolver el JSON final + headers.

👉 **No contiene lógica de negocio del agente**.

---

### 2. `xpander_handler.py`
Responsable de:
- Ejecutarse **solo cuando usás Xpander Dev / Workers**.
- Tomar la configuración del agente desde la UI.
- Inyectar contexto interno (intent, score).
- Ejecutar el LLM.
- Asegurar salida JSON válida.

👉 **No se usa en el flujo HTTP local**, pero es el mismo agente lógico.

---

### 3. `intent_classifier.py`
- Clasificador determinístico (sin LLM).
- Extrae:
  - `intent.id`
  - `intent.label`
  - `score` (0–100)
  - `reasons`

Se usa para:
- Headers HTTP.
- Ruteo futuro.
- Priorización comercial.

---

## Contrato de salida (JSON)

El agente devuelve **un único objeto JSON** con esta forma (flexible, no estricta):

```json
{
  "summary": "string",
  "assumptions": ["string"],
  "missing_questions": ["string"],
  "mvp_plan": [
    { "step": "string", "effort": "Bajo|Medio|Alto|1h|2d" }
  ],
  "risks": ["string"]
}
```

Campos adicionales pueden existir internamente, pero **la API solo expone este bloque**.

---

## Headers de respuesta

```http
x-intent-id: lead_automation
x-intent-score: 98
x-intent-reasons: ["has_budget", "has_urgency", ...]
```

---

## Variables de entorno

```env
# Seguridad
INTAKE_API_KEY=LEVONS_INTERNAL

# Xpander
XPANDER_API_KEY=xxxxxxxx
XPANDER_AGENT_ID=cd6c4b5c-8005-4c44-9e70-5831cefa608b
XPANDER_BASE_URL=https://api.xpander.ai
XPANDER_INVOKE_PATH=/v1/agents/{AGENT_ID}/invoke

# Runtime
INVOKE_TIMEOUT=60
```

---

## Ejecución local

### 1. Crear entorno
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Levantar API
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 3. Probar
```bash
curl -s http://127.0.0.1:8000/invoke \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: LEVONS_INTERNAL" \\
  -d '{"message":"implementar n8n para mi empresa"}'
```

---

## Docker

```bash
docker build -t intake-agent .
docker run -p 8000:8000 --env-file .env intake-agent
```

---

## Qué NO hace este proyecto (por diseño)

- No persiste conversaciones.
- No usa estado interno.
- No depende del SDK de Xpander en runtime HTTP.
- No fuerza strict JSON con retries agresivos (se prioriza resiliencia).

---

## Evoluciones naturales

- Ruteo por intent (agents especializados).
- Webhooks post-respuesta (CRM / Slack).
- Score → pipeline comercial.
- Versionado de prompts.
- Multi-tenant (org_id).

---

## Filosofía

> **Xpander define el “qué” (inteligencia).  
> Tu servidor controla el “cómo” (cómputo, seguridad, costos).**

---

## Estado actual

✅ Producción funcional  
✅ Cloudflare + Docker  
✅ Configurable desde UI sin redeploy  
✅ Resiliente a salidas inválidas del modelo  
"""

path = Path("/mnt/data/README.md")
path.write_text(content, encoding="utf-8")

path