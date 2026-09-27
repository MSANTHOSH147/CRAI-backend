"""
CRAI LOCAL FARMER ADVISORY

Qwen3 is an explanation-only layer.

AUTHORITATIVE CRAI OUTPUTS:
- disease prediction
- disease-model confidence
- field risk score
- risk level
- assessment confidence
- deterministic decision
- priority
- sensor values
- spatial evidence
- temporal evidence

Qwen3 NEVER calculates or changes CRAI risk.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests


# ============================================================
# CONFIG
# ============================================================

OLLAMA_BASE_URL = os.getenv(
    "CRAI_OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
).rstrip("/")

# CRAI uses Ollama /api/chat for local Qwen advisory generation.
OLLAMA_GENERATE_URL = (
    f"{OLLAMA_BASE_URL}/api/generate"
)

OLLAMA_TAGS_URL = (
    f"{OLLAMA_BASE_URL}/api/tags"
)

OLLAMA_MODEL = os.getenv(
    "CRAI_OLLAMA_MODEL",
    "qwen3:1.7b",
)

# Qwen3 1.7B can be slow on CPU.
OLLAMA_TIMEOUT_SECONDS = int(
    os.getenv(
        "CRAI_OLLAMA_TIMEOUT",
        "45",
    )
)

# Slightly higher than the previous 220 to reduce
# incomplete five-section responses.
MAX_OUTPUT_TOKENS = int(
    os.getenv(
        "CRAI_OLLAMA_MAX_TOKENS",
        "160",
        
    )
)

OLLAMA_KEEP_ALIVE = os.getenv(
    "CRAI_OLLAMA_KEEP_ALIVE",
    "10m",
)


# ============================================================
# LANGUAGE
# ============================================================

SUPPORTED_LANGUAGES = {
    "english": "English",
    "en": "English",

    "tamil": "Tamil",
    "ta": "Tamil",

    "hindi": "Hindi",
    "hi": "Hindi",
}


def normalize_language(
    language: Optional[str],
) -> str:

    if not language:
        return "English"

    return SUPPORTED_LANGUAGES.get(
        str(language).strip().lower(),
        "English",
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe(value: Any) -> Any:

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, dict):

        return {
            str(k): _safe(v)
            for k, v in value.items()
        }

    if isinstance(value, list):

        return [
            _safe(v)
            for v in value
        ]

    return str(value)


def _first(*values: Any) -> Any:

    for value in values:

        if value is not None:
            return value

    return None


def _number(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _round_number(
    value: Any,
    digits: int = 2,
) -> Optional[float]:

    number = _number(value)

    if number is None:
        return None

    return round(number, digits)


# ============================================================
# FIELD DATA NORMALIZATION
# ============================================================

def build_farmer_guidance(
    field_data: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(
        field_data,
        dict,
    ):
        field_data = {}

    disease = (
        field_data.get("disease")
        if isinstance(
            field_data.get("disease"),
            dict,
        )
        else {}
    )

    risk = (
        field_data.get("risk")
        if isinstance(
            field_data.get("risk"),
            dict,
        )
        else {}
    )

    decision = (
        field_data.get("decision")
        if isinstance(
            field_data.get("decision"),
            dict,
        )
        else {}
    )

    context = (
        field_data.get("context")
        if isinstance(
            field_data.get("context"),
            dict,
        )
        else {}
    )

    sensor = (
        context.get("sensor")
        if isinstance(
            context.get("sensor"),
            dict,
        )
        else {}
    )

    spatial = (
        context.get("spatial")
        if isinstance(
            context.get("spatial"),
            dict,
        )
        else {}
    )

    temporal = (
        context.get("temporal")
        if isinstance(
            context.get("temporal"),
            dict,
        )
        else {}
    )

    prediction = _first(
        disease.get("prediction"),
        disease.get("disease"),
        field_data.get("disease_signal"),
        field_data.get("prediction"),
    )

    confidence = _first(
        disease.get("confidence"),
        disease.get("model_confidence"),
        field_data.get("model_confidence"),
        field_data.get("confidence"),
    )

    risk_score = _first(
        risk.get("risk_score"),
        field_data.get("field_risk"),
        field_data.get("risk_score"),
    )

    risk_level = _first(
        risk.get("risk_level"),
        field_data.get("risk_level"),
    )

    assessment_confidence = _first(
        risk.get("assessment_confidence"),
        field_data.get("assessment_confidence"),
    )

    soil_moisture = _first(
        sensor.get("soil_moisture"),
        field_data.get("soil_moisture"),
    )

    temperature = _first(
        sensor.get("temperature"),
        field_data.get("temperature"),
    )

    humidity = _first(
        sensor.get("humidity"),
        field_data.get("humidity"),
    )

    timestamp = _first(
        sensor.get("timestamp"),
        field_data.get("sensor_timestamp"),
    )

    freshness = _first(
        sensor.get("freshness"),
        field_data.get("sensor_freshness"),
    )

    age_minutes = _first(
        sensor.get("age_minutes"),
        field_data.get("sensor_age_minutes"),
    )

    usable = _first(
        sensor.get("usable"),
        field_data.get("sensor_usable"),
    )

    infected = _first(
        spatial.get("infected_neighbors"),
        field_data.get("infected_neighbor_count"),
    )

    total = _first(
        spatial.get("total_observed_zones"),
        spatial.get("total_neighbor_count"),
        field_data.get("total_neighbor_count"),
    )

    if (
        infected is not None
        and total is not None
    ):

        try:

            spatial_signal = (
                f"{int(infected)} of "
                f"{int(total)} observed "
                f"zones affected"
            )

        except (
            TypeError,
            ValueError,
        ):

            spatial_signal = None

    else:

        spatial_signal = _first(
            field_data.get("spatial_signal")
        )

    temporal_trend = _first(
        temporal.get("trend"),
        field_data.get("temporal_trend"),
    )

    observation_count = _first(
        temporal.get("observation_count"),
        field_data.get("observation_count"),
    )

    recommended_steps = _first(
        decision.get("recommended_steps"),
        field_data.get("recommended_steps"),
    )

    if not isinstance(
        recommended_steps,
        list,
    ):
        recommended_steps = None

    return {
        "crop": _first(
            field_data.get("crop"),
            "Tomato",
        ),

        "growth_stage": _first(
            field_data.get("growth_stage"),
            "Vegetative",
        ),

        "zone": _first(
            field_data.get("zone"),
            field_data.get("zone_id"),
        ),

        "disease_signal": prediction,

        "model_confidence":
            _round_number(confidence),

        "field_risk":
            _round_number(risk_score),

        "risk_level":
            risk_level,

        "assessment_confidence":
            assessment_confidence,

        "sensor": {
            "soil_moisture":
                _round_number(soil_moisture),

            "temperature":
                _round_number(temperature),

            "humidity":
                _round_number(humidity),

            "timestamp":
                timestamp,

            "freshness":
                freshness,

            "age_minutes":
                _round_number(age_minutes),

            "usable":
                usable,
        },

        "spatial_signal":
            spatial_signal,

        "temporal_trend":
            temporal_trend,

        "observation_count":
            observation_count,

        "decision":
            _first(
                decision.get("action"),
                field_data.get("decision"),
            ),

        "decision_priority":
            _first(
                decision.get("priority"),
                field_data.get("decision_priority"),
            ),

        "recommended_steps":
            recommended_steps,

        "evidence_quality":
            field_data.get("evidence_quality"),

        "uncertainty":
            field_data.get("uncertainty"),
    }


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are CRAI's farmer advisory explanation assistant.

CRAI deterministic outputs are authoritative. You ONLY explain the supplied evidence.
Never calculate, recalculate, change, or reinterpret risk, confidence, decision, priority,
sensor values, spatial evidence, or temporal evidence.

IMPORTANT:
- Visual disease signal comes from the disease model.
- Environmental values come from sensors.
- Spatial evidence comes from field observations.
- Temporal trend describes CRAI field-risk observations over time, NOT disease-model confidence.
- STABLE means stable. Never call STABLE worsening, improving, increasing, decreasing, spreading, or deteriorating.
- Never invent missing values, treatments, pesticides, dosages, weather, or other interventions.
- Use only the supplied recommended_steps.
- A disease signal is a model/visual signal, not laboratory confirmation.
- If risk is CRITICAL, say CRAI's deterministic evidence-fusion engine classified it as CRITICAL.

LANGUAGE:
Use ONLY the requested farmer language. English = English. Tamil = Tamil. Hindi = Hindi.
Technical identifiers such as CRAI, Tomato, Tomato_Late_Blight, numbers, %, °C and RH may remain unchanged.

OUTPUT:
Return exactly five sections. Use the exact headings supplied by the user prompt.
Keep every section short. Finish all five sections.
"""


# ============================================================
# LANGUAGE RULES
# ============================================================

LANGUAGE_RULES = {

    "English": """
Write natural, simple English for a farmer.
Use short sentences.
Avoid unnecessary technical jargon.
""",

    "Tamil": """
முழுவதும் எளிய, இயல்பான தமிழில் எழுதவும்.

விவசாயி எளிதாக புரிந்து கொள்ளும் வகையில்
சிறிய வாக்கியங்களைப் பயன்படுத்தவும்.

ஆங்கில வாக்கியங்களை பயன்படுத்த வேண்டாம்.

Tomato, Tomato_Late_Blight, CRAI போன்ற
crop/disease/technical identifiers மற்றும்
எண்கள், %, °C, RH போன்ற அளவுகளை அப்படியே வைத்திருக்கலாம்.
""",

    "Hindi": """
पूरी तरह सरल और स्वाभाविक हिन्दी में लिखें।

किसान आसानी से समझ सके ऐसे छोटे वाक्यों का
उपयोग करें।

अंग्रेज़ी के सामान्य वाक्य न लिखें।

Tomato, Tomato_Late_Blight, CRAI जैसे
crop/disease/technical identifiers तथा
संख्या, %, °C, RH जैसी इकाइयों को वैसा ही रख सकते हैं।
""",
}


# ============================================================
# PROMPT BUILDER
# ============================================================

def build_advisory_prompt(
    field_data: Dict[str, Any],
    language: str = "English",
) -> str:

    language = normalize_language(language)
    evidence = build_farmer_guidance(field_data)

    payload = json.dumps(
        _safe(evidence),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    if language == "Tamil":
        headings = """
நிலைமை:
CRAI ஏன் கவலைப்படுகிறது:
இப்போது செய்ய வேண்டியது:
அடுத்த சரிபார்ப்பு:
எச்சரிக்கை:
"""
        language_instruction = """
முழு பதிலும் எளிய இயல்பான தமிழில் மட்டுமே இருக்க வேண்டும்.
ஆங்கில வாக்கியங்களை எழுத வேண்டாம்.
CRAI, Tomato, Tomato_Late_Blight, CRITICAL, HIGH, எண்கள், %, °C, RH போன்ற technical identifiers மட்டும் அப்படியே இருக்கலாம்.
STABLE என்றால் நிலையான போக்கு என்று மட்டும் கூறவும். அதை மோசமடைவது அல்லது அதிகரிப்பது என்று கூறக்கூடாது.
கொடுக்கப்பட்ட recommended_steps மட்டும் பயன்படுத்தவும்.
"""

    elif language == "Hindi":
        headings = """
स्थिति:
CRAI क्यों चिंतित है:
अभी क्या करें:
अगली जाँच:
सावधानी:
"""
        language_instruction = """
पूरा उत्तर सरल और स्वाभाविक हिन्दी में ही होना चाहिए।
अंग्रेज़ी के सामान्य वाक्य न लिखें।
CRAI, Tomato, Tomato_Late_Blight, CRITICAL, HIGH, संख्या, %, °C और RH जैसे technical identifiers वैसे ही रख सकते हैं।
STABLE का अर्थ केवल स्थिर प्रवृत्ति है। इसे बिगड़ना या बढ़ना न कहें।
केवल दिए गए recommended_steps का उपयोग करें।
"""

    else:
        headings = """
Situation:
Why CRAI is concerned:
What to do now:
Next check:
Caution:
"""
        language_instruction = """
Write only simple, natural English.
STABLE means a stable field-risk trend. Never describe it as worsening, improving, increasing, decreasing, spreading, or deteriorating.
Use only the supplied recommended_steps.
"""

    return f"""
Create a short farmer advisory using ONLY the authoritative CRAI evidence below.

REQUESTED LANGUAGE: {language}

{language_instruction}

AUTHORITATIVE EVIDENCE:
{payload}

STRICT RULES:
1. Do not calculate or change risk.
2. Do not change risk level, assessment confidence, decision, or priority.
3. Do not invent sensor values or facts.
4. Do not invent treatments, pesticides, dosages, weather, or interventions.
5. Do not invent a trend. Use temporal_trend exactly as supplied.
6. If temporal_trend is STABLE, describe it only as stable.
7. Do not confuse temporal trend with disease-model confidence.
8. Use only the supplied recommended_steps.
9. The visual disease signal is not laboratory confirmation.
10. Complete every section. Do not stop early.
11. Each section should be one short sentence, except What to do now, which may contain up to three numbered actions.
12. Do not add any sections before or after the five required sections.

OUTPUT HEADINGS:
{headings}
"""


# ============================================================
# CLEAN OUTPUT
# ============================================================

def _clean_model_output(
    text: Any,
) -> str:

    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"^```(?:text)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text.strip()


# ============================================================
# MODEL OUTPUT VALIDATION
# ============================================================

def _contains_any(
    text: str,
    patterns,
) -> bool:

    lowered = text.lower()

    return any(
        pattern.lower() in lowered
        for pattern in patterns
    )


def _has_required_sections(
    text: str,
    language: str,
) -> bool:

    if not text:
        return False

    if language == "English":

        required = [
            "Situation:",
            "Why CRAI is concerned:",
            "What to do now:",
            "Next check:",
            "Caution:",
        ]

    elif language == "Tamil":

        required = [
            "நிலைமை:",
            "CRAI ஏன் கவலைப்படுகிறது:",
            "இப்போது செய்ய வேண்டியது:",
            "அடுத்த சரிபார்ப்பு:",
            "எச்சரிக்கை:",
        ]

    else:

        required = [
            "स्थिति:",
            "CRAI क्यों चिंतित है:",
            "अभी क्या करें:",
            "अगली जाँच:",
            "सावधानी:",
        ]

    return all(
        section in text
        for section in required
    )


def _validate_language(
    text: str,
    language: str,
) -> bool:

    if not text:
        return False

    language = normalize_language(language)

    # English does not require a script check.
    if language == "English":
        return True

    # Remove technical tokens that are intentionally allowed
    # to remain in English across all farmer languages.
    cleaned = text

    allowed_terms = [
        "CRAI",
        "Tomato",
        "Tomato_Late_Blight",
        "CRITICAL",
        "HIGH",
        "MODERATE",
        "LOW",
        "RH",
        "°C",
        "%",
        "model",
        "deterministic",
        "evidence-fusion",
        "engine",
        "field",
        "risk",
        "trend",
        "observations",
        "laboratory",
        "confirmation",
    ]

    for term in allowed_terms:
        cleaned = cleaned.replace(term, " ")

    # ---------------------------------------------------------
    # Tamil
    # ---------------------------------------------------------
    if language == "Tamil":

        tamil_chars = sum(
            "\u0B80" <= ch <= "\u0BFF"
            for ch in cleaned
        )

        meaningful_chars = sum(
            ch.isalpha()
            for ch in cleaned
        )

        if meaningful_chars == 0:
            return False

        # At least 30% of meaningful alphabetic content
        # should be Tamil after technical-token removal.
        return (
            tamil_chars / meaningful_chars
        ) >= 0.30

    # ---------------------------------------------------------
    # Hindi
    # ---------------------------------------------------------
    if language == "Hindi":

        devanagari_chars = sum(
            "\u0900" <= ch <= "\u097F"
            for ch in cleaned
        )

        meaningful_chars = sum(
            ch.isalpha()
            for ch in cleaned
        )

        if meaningful_chars == 0:
            return False

        return (
            devanagari_chars / meaningful_chars
        ) >= 0.30

    return False
def _validate_trend(
    text: str,
    evidence: Dict[str, Any],
    language: str,
) -> bool:

    trend = evidence.get(
        "temporal_trend"
    )

    if not trend:
        return True

    trend = str(trend).strip().upper()

    lowered = text.lower()

    # --------------------------------------------------------
    # English
    # --------------------------------------------------------

    if language == "English":

        if trend == "DECREASING":

            forbidden = [
                "worsening",
                "getting worse",
                "increasing risk",
                "increased risk",
                "rising risk",
                "risk is increasing",
                "risk increased",
                "deteriorating",
                "deterioration",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "decreasing",
                "decreased",
                "declining",
                "declined",
                "lower",
                "reducing",
                "reduced",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "INCREASING":

            forbidden = [
                "decreasing",
                "declining",
                "lower risk",
                "risk is decreasing",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "increasing",
                "increased",
                "rising",
                "growing",
                "higher risk",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "STABLE":

            forbidden = [
                "increasing",
                "increased",
                "rising",
                "decreasing",
                "decreased",
                "declining",
                "declined",
                "worsening",
                "getting worse",
                "spreading",
                "deteriorating",
                "improving",
                "getting better",
            ]

            return not _contains_any(
                text,
                forbidden,
            )

        return True

    # --------------------------------------------------------
    # Tamil
    # --------------------------------------------------------

    if language == "Tamil":

        if trend == "DECREASING":

            forbidden = [
                "மோசமாக",
                "அதிகரித்து",
                "அதிகரிக்கும்",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "குறைந்து",
                "குறைகிறது",
                "குறைவாக",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "INCREASING":

            forbidden = [
                "குறைந்து",
                "குறைகிறது",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "அதிகரித்து",
                "அதிகரிக்கிறது",
                "உயர்ந்து",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "STABLE":

            return not _contains_any(
                text,
                [
                    "அதிகரித்து",
                    "அதிகரிக்கிறது",
                    "குறைந்து",
                    "குறைகிறது",
                ],
            )

        return True

    # --------------------------------------------------------
    # Hindi
    # --------------------------------------------------------

    if language == "Hindi":

        if trend == "DECREASING":

            forbidden = [
                "बढ़ रहा",
                "बढ़ती",
                "बिगड़",
                "खराब",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "कम हो",
                "कम हो रहा",
                "घट",
                "कमी",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "INCREASING":

            forbidden = [
                "कम हो रहा",
                "घट",
                "स्थिर",
            ]

            if _contains_any(
                text,
                forbidden,
            ):
                return False

            acceptable = [
                "बढ़",
                "बढ़ रहा",
                "बढ़ती",
                "ऊपर",
            ]

            return _contains_any(
                text,
                acceptable,
            )

        if trend == "STABLE":

            return not _contains_any(
                text,
                [
                    "बढ़ रहा",
                    "बढ़ती",
                    "कम हो रहा",
                    "घट",
                ],
            )

        return True

    return True



def _validate_grounding(
    text: str,
    evidence: Dict[str, Any],
    language: str,
) -> bool:
    """Reject obvious contradictions to authoritative CRAI outputs."""

    if not text:
        return False

    risk_level = evidence.get("risk_level")
    decision = evidence.get("decision")

    if risk_level:
        level = str(risk_level).strip().upper()

        if level == "CRITICAL" and _contains_any(
            text,
            [
                "low risk",
                "low field risk",
                "moderate risk",
                "moderate field risk",
                "risk is low",
            ],
        ):
            return False

        if level == "HIGH" and _contains_any(
            text,
            [
                "low risk",
                "low field risk",
                "critical risk instead",
            ],
        ):
            return False

        if level == "MODERATE" and _contains_any(
            text,
            [
                "low risk",
                "critical risk",
            ],
        ):
            return False

    if decision:
        normalized = str(decision).strip().upper()

        if normalized == "PRIORITIZE_INSPECTION" and _contains_any(
            text,
            [
                "no inspection needed",
                "inspection is unnecessary",
                "do not inspect",
                "ignore the affected area",
            ],
        ):
            return False

    return True


def _validate_risk_and_decision(
    text: str,
    evidence: Dict[str, Any],
) -> bool:

    risk_level = evidence.get(
        "risk_level"
    )

    decision = evidence.get(
        "decision"
    )

    # --------------------------------------------------------
    # Risk level
    # --------------------------------------------------------

    if risk_level:

        normalized_level = str(
            risk_level
        ).strip().upper()

        # Prevent common contradiction patterns.
        if normalized_level == "CRITICAL":

            contradictory = [
                "low risk",
                "low field risk",
                "moderate risk",
                "moderate field risk",
                "high risk instead",
            ]

            if _contains_any(
                text,
                contradictory,
            ):
                return False

        elif normalized_level == "HIGH":

            contradictory = [
                "low risk",
                "low field risk",
                "critical risk instead",
            ]

            if _contains_any(
                text,
                contradictory,
            ):
                return False

    # --------------------------------------------------------
    # Decision
    # --------------------------------------------------------

    if decision:

        normalized_decision = str(
            decision
        ).strip().upper()

        if normalized_decision == "PRIORITIZE_INSPECTION":

            contradictory = [
                "no inspection needed",
                "inspection is unnecessary",
                "do not inspect",
                "ignore the affected area",
            ]

            if _contains_any(
                text,
                contradictory,
            ):
                return False

    return True


def _validate_model_output(
    text: str,
    evidence: Dict[str, Any],
    language: str,
) -> bool:
    """
    Validate that Qwen produced a usable explanation.

    IMPORTANT:
    Qwen is NOT responsible for CRAI risk calculation.
    This validator only rejects obvious contradictions,
    hallucinations, or empty output.

    We intentionally do NOT require exact section headings.
    Small local models such as qwen3:1.7b may return a
    natural paragraph even when the prompt requests sections.
    """

    if not text or not str(text).strip():
        return False
        # Reject responses that contain only headings with no content.
    section_markers = {
        "English": [
            "Situation:",
            "Why CRAI is concerned:",
            "What to do now:",
            "Next check:",
            "Caution:",
        ],
        "Tamil": [
            "நிலைமை:",
            "CRAI ஏன் கவலைப்படுகிறது:",
            "இப்போது செய்ய வேண்டியது:",
            "அடுத்த சரிபார்ப்பு:",
            "எச்சரிக்கை:",
        ],
        "Hindi": [
            "स्थिति:",
            "CRAI क्यों चिंतित है:",
            "अभी क्या करें:",
            "अगली जाँच:",
            "सावधानी:",
        ],
    }

    markers = section_markers.get(
        normalize_language(language),
        section_markers["English"],
    )

    # If the model returned headings, require actual content
    # after at least one heading.
    heading_count = sum(
        1 for marker in markers
        if marker in text
    )

    if heading_count >= 3:
        content_chars = 0

        for marker in markers:
            if marker in text:
                after = text.split(marker, 1)[1].strip()

                # Remove the next heading if present.
                for next_marker in markers:
                    if next_marker != marker and next_marker in after:
                        after = after.split(next_marker, 1)[0]

                content_chars += len(after.strip())

        if content_chars < 40:
            return False
    text = str(text).strip()

    # --------------------------------------------------------
    # Reject obvious instruction leakage / unsafe output
    # --------------------------------------------------------

    suspicious_patterns = [
        "ignore previous instructions",
        "ignore the instructions",
        "ignore all instructions",
        "as an ai",
        "i cannot follow",
        "i am unable",
        "laboratory confirmed",
        "lab confirmed",
    ]

    if _contains_any(text, suspicious_patterns):
        return False

    # --------------------------------------------------------
    # Validate authoritative CRAI risk / decision grounding
    # --------------------------------------------------------

    if not _validate_grounding(
        text,
        evidence,
        language,
    ):
        return False

    if not _validate_risk_and_decision(
        text,
        evidence,
    ):
        return False

    # --------------------------------------------------------
    # Validate temporal interpretation when available.
    #
    # This prevents Qwen from turning STABLE into worsening,
    # increasing, decreasing, spreading, etc.
    # --------------------------------------------------------

    if not _validate_trend(
        text,
        evidence,
        language,
    ):
        return False

    # --------------------------------------------------------
    # Do NOT reject a valid response merely because:
    #
    # - it lacks exact headings
    # - it is a paragraph
    # - Qwen uses a slightly different sentence structure
    #
    # The deterministic CRAI evidence remains authoritative.
    # --------------------------------------------------------

    return True


# ============================================================
# FALLBACK HELPERS
# ============================================================

def _fallback_value(
    value: Any,
    default: str = "—",
) -> str:

    if value is None:
        return default

    return str(value)


# ============================================================
# FALLBACK ADVISORY
# ============================================================

def build_fallback_advisory(
    field_data: Dict[str, Any],
    language: str = "English",
) -> str:

    language = normalize_language(language)

    evidence = build_farmer_guidance(
        field_data
    )

    crop = _fallback_value(
        evidence.get("crop"),
        "crop",
    )

    zone = _fallback_value(
        evidence.get("zone"),
        "zone",
    )

    disease = _fallback_value(
        evidence.get("disease_signal"),
        "visual disease signal",
    )

    confidence = evidence.get(
        "model_confidence"
    )

    risk = evidence.get(
        "field_risk"
    )

    risk_level = _fallback_value(
        evidence.get("risk_level"),
        "UNAVAILABLE",
    )

    assessment_confidence = _fallback_value(
        evidence.get("assessment_confidence"),
        "UNAVAILABLE",
    )

    sensor = evidence.get(
        "sensor"
    ) or {}

    soil = sensor.get(
        "soil_moisture"
    )

    temp = sensor.get(
        "temperature"
    )

    humidity = sensor.get(
        "humidity"
    )

    spatial = evidence.get(
        "spatial_signal"
    )

    trend = evidence.get(
        "temporal_trend"
    )

    steps = evidence.get(
        "recommended_steps"
    ) or []

    # ========================================================
    # ENGLISH FALLBACK
    # ========================================================

    if language == "English":

        situation = (
            f"CRAI detected a visual signal of "
            f"{disease} in {crop} at {zone}."
        )

        if confidence is not None:

            situation += (
                f" Model confidence is "
                f"{confidence:.2f}%."
            )

        why = (
            f"The disease model detected a visual signal. "
            f"CRAI's deterministic evidence-fusion engine "
            f"classified field risk as {risk_level}"
        )

        if risk is not None:

            why += f" at {risk:.1f}."

        else:

            why += "."

        why += (
            f" Assessment confidence is "
            f"{assessment_confidence}."
        )

        if spatial:

            why += (
                f" Spatial evidence: {spatial}."
            )

        if trend:

            trend_map = {
                "INCREASING":
                    "increasing",

                "DECREASING":
                    "decreasing",

                "STABLE":
                    "stable",
            }

            trend_text = trend_map.get(
                str(trend).upper(),
                str(trend).lower(),
            )

            why += (
                f" Recent CRAI observations show "
                f"a {trend_text} trend."
            )

        sensor_parts = []

        if soil is not None:

            sensor_parts.append(
                f"soil moisture {soil:.1f}%"
            )

        if temp is not None:

            sensor_parts.append(
                f"temperature {temp:.1f}°C"
            )

        if humidity is not None:

            sensor_parts.append(
                f"humidity {humidity:.1f}% RH"
            )

        if sensor_parts:

            why += (
                " Current conditions: "
                + ", ".join(sensor_parts)
                + "."
            )

        if steps:

            actions = "\n".join(
                f"{i}. {step}"
                for i, step in enumerate(
                    steps[:4],
                    1,
                )
            )

        else:

            actions = (
                "1. Inspect the affected area.\n"
                "2. Follow the CRAI decision.\n"
                "3. Re-observe the zone."
            )

        return (
            f"Situation: {situation}\n\n"

            f"Why CRAI is concerned: {why}\n\n"

            f"What to do now:\n{actions}\n\n"

            f"Next check: Re-observe the affected "
            f"zone after the recommended action.\n\n"

            f"Caution: The disease signal is a "
            f"visual/model prediction, not laboratory "
            f"confirmation."
        )

    # ========================================================
    # TAMIL FALLBACK
    # ========================================================

    if language == "Tamil":

        situation = (
            f"{zone} பகுதியில் உள்ள {crop} பயிரில் "
            f"{disease} தொடர்பான காட்சி அறிகுறியை "
            f"CRAI கண்டறிந்துள்ளது."
        )

        if confidence is not None:

            situation += (
                f" நோய் மாதிரி நம்பிக்கை "
                f"{confidence:.2f}%."
            )

        why = (
            f"நோய் மாதிரி காட்சி அறிகுறியை "
            f"கண்டறிந்துள்ளது. CRAI-யின் "
            f"deterministic evidence-fusion engine "
            f"வயல் அபாயத்தை {risk_level} என்று "
            f"வகைப்படுத்தியுள்ளது"
        )

        if risk is not None:

            why += (
                f" ({risk:.1f})."
            )

        else:

            why += "."

        why += (
            f" மதிப்பீட்டு நம்பிக்கை "
            f"{assessment_confidence}."
        )

        if spatial:

            why += (
                f" இடவியல் தகவல்: {spatial}."
            )

        if trend:

            trend_map = {

                "INCREASING":
                    "அதிகரித்து வரும்",

                "DECREASING":
                    "குறைந்து வரும்",

                "STABLE":
                    "நிலையான",
            }

            tamil_trend = trend_map.get(
                str(trend).upper(),
                "மாற்றம் உள்ள",
            )

            why += (
                f" சமீபத்திய CRAI பதிவுகளில் "
                f"{tamil_trend} போக்கு உள்ளது."
            )

        sensor_parts = []

        if soil is not None:

            sensor_parts.append(
                f"மண் ஈரப்பதம் {soil:.1f}%"
            )

        if temp is not None:

            sensor_parts.append(
                f"வெப்பநிலை {temp:.1f}°C"
            )

        if humidity is not None:

            sensor_parts.append(
                f"காற்றின் ஈரப்பதம் {humidity:.1f}% RH"
            )

        if sensor_parts:

            why += (
                " தற்போதைய நிலை: "
                + ", ".join(sensor_parts)
                + "."
            )

        if steps:

            tamil_actions = []

            for step in steps[:4]:

                text = str(step)

                if "Inspect" in text:

                    tamil_actions.append(
                        "பாதிக்கப்பட்ட தாவரங்களை "
                        "முதலில் பரிசோதிக்கவும்."
                    )

                elif "irrigation" in text.lower():

                    tamil_actions.append(
                        "பாசனத் தேவையை சரிபார்க்கவும்."
                    )

                elif "Re-observe" in text:

                    tamil_actions.append(
                        "அந்த பகுதியை மீண்டும் கவனிக்கவும்."
                    )

                else:

                    tamil_actions.append(
                        "பரிந்துரைக்கப்பட்ட நடவடிக்கையை "
                        "பின்பற்றவும்."
                    )

            if not tamil_actions:

                tamil_actions = [
                    "பாதிக்கப்பட்ட பகுதியை பரிசோதிக்கவும்.",
                    "CRAI பரிந்துரைத்த முடிவைப் பின்பற்றவும்.",
                    "பின்னர் அந்த பகுதியை மீண்டும் கவனிக்கவும்.",
                ]

        else:

            tamil_actions = [
                "பாதிக்கப்பட்ட பகுதியை பரிசோதிக்கவும்.",
                "CRAI பரிந்துரைத்த முடிவைப் பின்பற்றவும்.",
                "பின்னர் அந்த பகுதியை மீண்டும் கவனிக்கவும்.",
            ]

        actions = "\n".join(
            f"{i}. {text}"
            for i, text in enumerate(
                tamil_actions[:4],
                1,
            )
        )

        return (
            f"நிலைமை: {situation}\n\n"

            f"CRAI ஏன் கவலைப்படுகிறது: {why}\n\n"

            f"இப்போது செய்ய வேண்டியது:\n{actions}\n\n"

            f"அடுத்த சரிபார்ப்பு: பரிந்துரைக்கப்பட்ட "
            f"நடவடிக்கைக்குப் பிறகு பாதிக்கப்பட்ட "
            f"பகுதியை மீண்டும் கவனிக்கவும்.\n\n"

            f"எச்சரிக்கை: இது காட்சி/மாதிரி அடிப்படையிலான "
            f"அறிகுறி மட்டுமே; ஆய்வக உறுதிப்படுத்தல் அல்ல."
        )

    # ========================================================
    # HINDI FALLBACK
    # ========================================================

    situation = (
        f"{zone} क्षेत्र में {crop} फसल में "
        f"{disease} का दृश्य संकेत CRAI ने पाया है।"
    )

    if confidence is not None:

        situation += (
            f" मॉडल का confidence {confidence:.2f}% है।"
        )

    why = (
        f"रोग मॉडल ने एक दृश्य संकेत पाया है। "
        f"CRAI के deterministic evidence-fusion engine "
        f"ने field risk को {risk_level} वर्गीकृत किया है"
    )

    if risk is not None:

        why += f" ({risk:.1f})।"

    else:

        why += "।"

    why += (
        f" मूल्यांकन confidence "
        f"{assessment_confidence} है।"
    )

    if spatial:

        why += (
            f" स्थानिक जानकारी: {spatial}।"
        )

    if trend:

        trend_map = {

            "INCREASING":
                "बढ़ता हुआ",

            "DECREASING":
                "कम होता हुआ",

            "STABLE":
                "स्थिर",
        }

        hindi_trend = trend_map.get(
            str(trend).upper(),
            "बदलता हुआ",
        )

        why += (
            f" हाल की CRAI observations में "
            f"{hindi_trend} trend है।"
        )

    sensor_parts = []

    if soil is not None:

        sensor_parts.append(
            f"मिट्टी की नमी {soil:.1f}%"
        )

    if temp is not None:

        sensor_parts.append(
            f"तापमान {temp:.1f}°C"
        )

    if humidity is not None:

        sensor_parts.append(
            f"हवा की नमी {humidity:.1f}% RH"
        )

    if sensor_parts:

        why += (
            " वर्तमान स्थिति: "
            + ", ".join(sensor_parts)
            + "।"
        )

    if steps:

        hindi_actions = []

        for step in steps[:4]:

            text = str(step)

            if "Inspect" in text:

                hindi_actions.append(
                    "प्रभावित पौधों की पहले जाँच करें।"
                )

            elif "irrigation" in text.lower():

                hindi_actions.append(
                    "सिंचाई की जरूरत जाँचें।"
                )

            elif "Re-observe" in text:

                hindi_actions.append(
                    "क्षेत्र को दोबारा देखें।"
                )

            else:

                hindi_actions.append(
                    "सुझाई गई कार्रवाई का पालन करें।"
                )

        if not hindi_actions:

            hindi_actions = [
                "प्रभावित क्षेत्र की जाँच करें।",
                "CRAI के सुझाए गए निर्णय का पालन करें।",
                "बाद में क्षेत्र को दोबारा देखें।",
            ]

    else:

        hindi_actions = [
            "प्रभावित क्षेत्र की जाँच करें।",
            "CRAI के सुझाए गए निर्णय का पालन करें।",
            "बाद में क्षेत्र को दोबारा देखें।",
        ]

    actions = "\n".join(
        f"{i}. {text}"
        for i, text in enumerate(
            hindi_actions[:4],
            1,
        )
    )

    return (
        f"स्थिति: {situation}\n\n"

        f"CRAI क्यों चिंतित है: {why}\n\n"

        f"अभी क्या करें:\n{actions}\n\n"

        f"अगली जाँच: सुझाई गई कार्रवाई के बाद "
        f"प्रभावित क्षेत्र को दोबारा देखें।\n\n"

        f"सावधानी: यह दृश्य/model संकेत है, "
        f"laboratory confirmation नहीं।"
    )


# ============================================================
# OLLAMA HEALTH
# ============================================================

def check_ollama() -> Dict[str, Any]:

    try:

        response = requests.get(
            OLLAMA_TAGS_URL,
            timeout=5,
        )

        if response.status_code != 200:

            return {
                "available": False,
                "model": OLLAMA_MODEL,
                "model_available": False,
                "models": [],
                "error":
                    f"Ollama HTTP {response.status_code}",
            }

        data = response.json()

        models = []

        for item in data.get("models") or []:

            if isinstance(item, dict):

                name = item.get("name")

                if name:
                    models.append(name)

        return {
            "available": True,
            "model": OLLAMA_MODEL,
            "model_available":
                OLLAMA_MODEL in models,
            "models": models,
        }

    except Exception as exc:

        return {
            "available": False,
            "model": OLLAMA_MODEL,
            "model_available": False,
            "models": [],
            "error": str(exc),
        }


# ============================================================
# GENERATE LOCAL ADVISORY
# ============================================================

def generate_local_advisory(
    field_data: Dict[str, Any],
    language: str = "English",
) -> Dict[str, Any]:

    language = normalize_language(language)

    grounded_evidence = build_farmer_guidance(
        field_data
    )

    fallback = build_fallback_advisory(
        field_data,
        language,
    )

    prompt = build_advisory_prompt(
        field_data,
        language,
    )

    # --------------------------------------------------------
    # CRAI ARCHITECTURE
    #
    # Qwen3 = explanation only.
    #
    # CRAI deterministic fusion remains authoritative for:
    # - risk score
    # - risk level
    # - assessment confidence
    # - decision
    # - recommended steps
    #
    # Qwen3 cannot calculate or modify these values.
    # --------------------------------------------------------

    payload = {
        "model": OLLAMA_MODEL,

        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        "stream": False,

        # CRAI performs the reasoning before Qwen.
        "think": False,

        "keep_alive": OLLAMA_KEEP_ALIVE,

        "options": {
            "temperature": 0.0,
            "top_p": 0.50,
            "num_predict": 220,
            "num_ctx": 2048,
            "repeat_penalty": 1.10,
        },
    }

    # Respect configured Ollama base URL.
    chat_url = f"{OLLAMA_BASE_URL}/api/chat"

    try:

        response = requests.post(
            chat_url,
            json=payload,
            timeout=(10, OLLAMA_TIMEOUT_SECONDS),
        )

        if response.status_code != 200:

            return {
                "available": False,
                "provider": "OLLAMA",
                "model": OLLAMA_MODEL,
                "language": language,
                "advisory": fallback,
                "grounded_evidence": grounded_evidence,
                "offline": True,
                "fallback": True,
                "error": (
                    f"Ollama HTTP "
                    f"{response.status_code}"
                ),
            }

        data = response.json()

        message = data.get("message") or {}

        advisory = _clean_model_output(
            message.get("content")
        )

        if not advisory:

            return {
                "available": False,
                "provider": "OLLAMA",
                "model": OLLAMA_MODEL,
                "language": language,
                "advisory": fallback,
                "grounded_evidence": grounded_evidence,
                "offline": True,
                "fallback": True,
                "error": "Ollama returned empty advisory.",
            }

        # ----------------------------------------------------
        # Strict validation.
        #
        # If Qwen violates CRAI grounding rules, NEVER expose
        # the generated text to the farmer.
        #
        # Use the deterministic advisory instead.
        # ----------------------------------------------------

        valid = _validate_model_output(
            advisory,
            grounded_evidence,
            language,
        )

        if not valid:

            return {
                "available": True,
                "provider": "OLLAMA",
                "model": OLLAMA_MODEL,
                "language": language,
                "advisory": fallback,
                "grounded_evidence": grounded_evidence,

                # Important:
                # Ollama itself responded successfully.
                # Therefore this is NOT an offline condition.
                "offline": False,
                "fallback": True,

                "error": (
                    "Qwen3 response did not satisfy "
                    "CRAI grounding validation. "
                    "Deterministic CRAI advisory used."
                ),
            }

        return {
            "available": True,
            "provider": "OLLAMA",
            "model": OLLAMA_MODEL,
            "language": language,
            "advisory": advisory,
            "grounded_evidence": grounded_evidence,
            "offline": False,
            "fallback": False,
            "error": None,
        }

    except requests.exceptions.Timeout:

        return {
            "available": False,
            "provider": "OLLAMA",
            "model": OLLAMA_MODEL,
            "language": language,
            "advisory": fallback,
            "grounded_evidence": grounded_evidence,
            "offline": True,
            "fallback": True,
            "error": (
                "Ollama chat generation timed out. "
                "Deterministic CRAI advisory used."
            ),
        }

    except requests.exceptions.RequestException as exc:

        return {
            "available": False,
            "provider": "OLLAMA",
            "model": OLLAMA_MODEL,
            "language": language,
            "advisory": fallback,
            "grounded_evidence": grounded_evidence,
            "offline": True,
            "fallback": True,
            "error": (
                f"Ollama connection error: {exc}"
            ),
        }

    except Exception as exc:

        return {
            "available": False,
            "provider": "OLLAMA",
            "model": OLLAMA_MODEL,
            "language": language,
            "advisory": fallback,
            "grounded_evidence": grounded_evidence,
            "offline": True,
            "fallback": True,
            "error": (
                f"Unexpected advisory error: {exc}"
            ),
        }