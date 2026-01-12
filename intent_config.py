# intent_config.py

INTENTS = [
    {
        "id": "lead_automation",
        "label": "Automatización de leads (CRM/Airtable/Slack)",
        "keywords": ["lead", "leads", "airtable", "slack", "crm", "form", "hubspot", "pipedrive"],
    },
    {
        "id": "customer_support_ai",
        "label": "Soporte al cliente con IA (tickets/FAQ/chatbot)",
        "keywords": ["soporte", "tickets", "zendesk", "intercom", "chatbot", "faq", "helpdesk"],
    },
    {
        "id": "data_pipelines",
        "label": "Pipelines/ETL/Integraciones de datos",
        "keywords": ["etl", "pipeline", "bigquery", "warehouse", "sync", "db", "postgres", "supabase"],
    },
    {
        "id": "growth_marketing_automation",
        "label": "Automatización Growth/Marketing (Ads/CRM/Segmentación)",
        "keywords": ["ads", "meta", "google ads", "braze", "email", "segment", "attribution", "appsflyer"],
    },
    {
        "id": "other",
        "label": "Otro / No clasificado",
        "keywords": [],
    },
]

# Scoring: 0 a 100 (prioridad comercial/operativa)
SCORING_RULES = {
    "has_budget": 25,          # menciona presupuesto o monto
    "has_urgency": 25,         # menciona urgencia/ASAP/alta
    "has_stack": 20,           # menciona herramientas concretas
    "has_scope": 20,           # describe proceso: "desde X hacia Y"
    "is_vague_penalty": -20,   # mensaje tipo "hola", "ping", "test"
}

URGENCY_KEYWORDS = ["urgente", "alta", "asap", "ya", "hoy", "mañana", "prioridad"]
VAGUE_KEYWORDS = ["ping", "test", "hola", "prueba"]