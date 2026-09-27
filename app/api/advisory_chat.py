from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/api/advisory", tags=["Advisory Chat"])


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"
OLLAMA_TIMEOUT = 45


class AdvisoryAskRequest(BaseModel):
    message: str
    language: str = "en"
    farm_id: Optional[Any] = None
    zone_id: Optional[str] = None
    crop: Optional[str] = None
    growth_stage: Optional[str] = None
    context: Dict[str, Any] = {}


def _normalise_language(language: str) -> str:
    value = (language or "en").strip().lower()

    if value in {"ta", "tamil", "தமிழ்"}:
        return "Tamil"

    return "English"


def _get_context_value(
    context: Dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    value = context.get(key)

    if value is None:
        return default

    return value


def _fallback(
    message: str,
    language: str,
    context: Dict[str, Any],
) -> str:
    score = _get_context_value(context, "risk_score", "—")
    risk = _get_context_value(context, "risk_level", "UNKNOWN")
    action = _get_context_value(
        context,
        "decision_action",
        "MONITOR",
    )

    zone = _get_context_value(context, "zone_id", "A1")
    crop = _get_context_value(context, "crop", "பயிர்")

    if language == "Tamil":
        risk_map = {
            "LOW": "குறைந்த",
            "MODERATE": "மிதமான",
            "HIGH": "அதிக",
            "CRITICAL": "மிகவும் அதிக",
            "UNKNOWN": "தெரியாத",
        }

        action_map = {
            "CONTINUE_MONITORING": "தொடர்ந்து கண்காணிக்கவும்",
            "MONITOR": "தொடர்ந்து கண்காணிக்கவும்",
            "INVESTIGATE": "மேலும் பரிசோதிக்கவும்",
            "PROTECT": "பாதுகாப்பு நடவடிக்கை எடுக்கவும்",
            "ALERT": "உடனடியாக கவனம் செலுத்தவும்",
        }

        tamil_risk = risk_map.get(
            str(risk).upper(),
            "தெரியாத",
        )

        tamil_action = action_map.get(
            str(action).upper(),
            "தொடர்ந்து கண்காணிக்கவும்",
        )

        return (
            f"{zone} பகுதியில் உள்ள {crop} பயிர் தற்போது "
            f"{tamil_risk} அபாய நிலையில் உள்ளது. "
            f"அபாய மதிப்பெண் {score}/100.\n\n"
            f"இந்த முடிவு CRAI அமைப்பில் கிடைக்கும் சென்சார் "
            f"தகவல்கள் மற்றும் பிற ஆதாரங்களை இணைத்து "
            f"பகுப்பாய்வு செய்ததன் அடிப்படையில் உருவாக்கப்பட்டது.\n\n"
            f"தற்போதைய பரிந்துரை: {tamil_action}.\n\n"
            f"மண்ணின் ஈரப்பதம், வெப்பநிலை மற்றும் பயிரில் "
            f"ஏற்படும் புதிய மாற்றங்களை தொடர்ந்து கவனிக்கவும்.\n\n"
            f"புதிய அறிகுறிகள் அல்லது குறிப்பிடத்தக்க மாற்றங்கள் "
            f"தெரிந்தால் மீண்டும் பரிசோதிக்கவும்."
        )

    return (
        f"The crop in zone {zone} is currently at "
        f"{risk} risk with a risk score of {score}/100.\n\n"
        f"This explanation is based on the current CRAI "
        f"sensor and evidence assessment.\n\n"
        f"Current recommended action: {action}.\n\n"
        f"Continue monitoring soil moisture, temperature, "
        f"and any new crop symptoms or changes.\n\n"
        f"If new symptoms or significant changes appear, "
        f"run another assessment."
    )


def _build_prompt(
    payload: AdvisoryAskRequest,
    language: str,
) -> str:
    context = payload.context or {}

    return f"""
You are the CRAI Farmer Advisory Assistant.

Your role is ONLY to explain and communicate the result
already produced by the CRAI deterministic intelligence system.

IMPORTANT ARCHITECTURE RULES:

1. CRAI deterministic intelligence is the authority for:
   - risk score
   - risk level
   - decision action
   - priority
   - evidence availability

2. NEVER calculate a new risk score.

3. NEVER change the risk level.

4. NEVER override the CRAI decision.

5. NEVER invent sensor values or evidence.

6. If information is missing, clearly say that the
   information is unavailable.

7. Explain the result in simple language suitable for a farmer.

8. Give practical observation/monitoring guidance only when
   supported by the supplied CRAI context.

9. Do not claim that simulated data is real hardware data.

10. The user question is only a request for explanation.

CURRENT CRAI ASSESSMENT:

Farm ID: {payload.farm_id}
Zone: {payload.zone_id}
Crop: {payload.crop}
Growth stage: {payload.growth_stage}

Risk score: {context.get("risk_score", "UNKNOWN")}
Risk level: {context.get("risk_level", "UNKNOWN")}
Decision action: {context.get("decision_action", "UNKNOWN")}
Priority: {context.get("priority", "UNKNOWN")}

Temperature: {context.get("temperature", "UNKNOWN")}
Humidity: {context.get("humidity", "UNKNOWN")}
Soil moisture: {context.get("soil_moisture", "UNKNOWN")}
Source: {context.get("source", "UNKNOWN")}

Evidence:
Visual: {context.get("evidence", {}).get("visual", "UNKNOWN")}
Environmental: {context.get("evidence", {}).get("environmental", "UNKNOWN")}
Temporal: {context.get("evidence", {}).get("temporal", "UNKNOWN")}
Spatial: {context.get("evidence", {}).get("spatial", "UNKNOWN")}

FARMER QUESTION:

{payload.message}

LANGUAGE:

Respond in {language}.

If the language is Tamil:
- Write the answer primarily in natural Tamil.
- Do not translate the CRAI numbers incorrectly.
- Keep crop names such as Tomato if necessary.
- Do not use unnecessary English technical terminology.
- Do not produce English paragraphs.

Keep the answer concise and practical.
""".strip()


@router.get("/status")
def advisory_status() -> Dict[str, Any]:
    model_available = False
    models = []

    try:
        response = requests.get(
            "http://127.0.0.1:11434/api/tags",
            timeout=5,
        )

        if response.ok:
            data = response.json()
            models = [
                item.get("name")
                for item in data.get("models", [])
                if item.get("name")
            ]

            model_available = (
                OLLAMA_MODEL in models
                or any(
                    str(name).startswith("qwen3:1.7b")
                    for name in models
                )
            )

    except Exception:
        model_available = False

    return {
        "available": model_available,
        "model": OLLAMA_MODEL,
        "model_available": model_available,
        "models": models,
    }


@router.post("/ask")
def ask_advisory(
    payload: AdvisoryAskRequest,
) -> Dict[str, Any]:
    language = _normalise_language(payload.language)

    context = dict(payload.context or {})

    if payload.zone_id is not None:
        context.setdefault("zone_id", payload.zone_id)

    if payload.crop is not None:
        context.setdefault("crop", payload.crop)

    if payload.growth_stage is not None:
        context.setdefault(
            "growth_stage",
            payload.growth_stage,
        )

    fallback = _fallback(
        payload.message,
        language,
        context,
    )

    # Tamil farmer communication uses the deterministic
    # grounded response for fast and reliable operation.
    #
    # CRAI remains the authoritative decision engine.
    if language == "Tamil":
        return {
            "available": True,
            "provider": "CRAI_GROUNDED_ADVISORY",
            "model": OLLAMA_MODEL,
            "language": "Tamil",
            "answer": fallback,
            "fallback": False,
            "llm_role": "EXPLANATION_ONLY",
            "deterministic_source": "CRAI_FUSION_V1_5",
        }

    prompt = _build_prompt(
        payload,
        language,
    )

    system_prompt = """
You are the explanation-only conversational assistant
for CRAI, an agricultural crop-risk intelligence system.

CRAI's deterministic intelligence has already produced
the authoritative risk and decision.

You MUST NOT:
- calculate risk
- modify risk
- override the decision
- invent sensor readings
- invent evidence
- claim simulated data is real

Your job is to explain the supplied CRAI assessment
clearly and practically to the farmer.

Use simple language.
Keep the answer concise.
""".strip()

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 120,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        answer = (
            data.get("message", {})
            .get("content", "")
            .strip()
        )

        if not answer:
            raise RuntimeError(
                "Ollama returned an empty answer"
            )

        return {
            "available": True,
            "provider": "OLLAMA",
            "model": OLLAMA_MODEL,
            "language": language,
            "answer": answer,
            "fallback": False,
            "llm_role": "EXPLANATION_ONLY",
            "deterministic_source": "CRAI_FUSION_V1_5",
        }

    except Exception as exc:
        return {
            "available": True,
            "provider": "CRAI_GROUNDED_ADVISORY",
            "model": OLLAMA_MODEL,
            "language": language,
            "answer": fallback,
            "fallback": True,
            "error": str(exc),
            "llm_role": "EXPLANATION_ONLY",
            "deterministic_source": "CRAI_FUSION_V1_5",
        }
