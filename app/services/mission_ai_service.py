from pathlib import Path

from app.services.ai_service import (
    predict_image,
)

from app.services.risk_service import (
    predict_risk,
)


# ============================================================
# PATHS
# ============================================================

BACKEND_DIR = (
    Path(__file__).resolve().parents[2]
)

PLANTDOC_DIR = (
    BACKEND_DIR
    / "AI_HANDOFF"
    / "plantdoc"
    / "train"
)


# ============================================================
# SUPPORTED CRAI DATASET CLASSES
# ============================================================

DATASET_CLASSES = {

    "Potato_Early_Blight":
        "Potato leaf early blight",

    "Potato_Late_Blight":
        "Potato leaf late blight",

    "Tomato_Early_Blight":
        "Tomato Early blight leaf",

    "Tomato_Healthy":
        "Tomato leaf",

    "Tomato_Bacterial_Spot":
        "Tomato leaf bacterial spot",

    "Tomato_Late_Blight":
        "Tomato leaf late blight",

    "Tomato_Mosaic_Virus":
        "Tomato leaf mosaic virus",

    "Tomato_Yellow_Virus":
        "Tomato leaf yellow virus",

    "Tomato_Leaf_Mold":
        "Tomato mold leaf",

    "Tomato_Septoria_Leaf_Spot":
        "Tomato Septoria leaf spot",
}


# ============================================================
# MISSION SOURCE PLAN
# ============================================================
#
# IMPORTANT:
#
# This mapping ONLY chooses which real PlantDoc image is
# presented to the Disease AI during the prototype mission.
#
# It does NOT determine the Disease AI prediction.
#
# Disease AI independently predicts the disease.
#
# Risk AI independently calculates the risk.
#
# ============================================================

MISSION_PLAN = {

    "A1":
        "Tomato_Healthy",

    "A2":
        "Tomato_Early_Blight",

    "A3":
        "Tomato_Bacterial_Spot",

    "A4":
        "Tomato_Late_Blight",

    "A5":
        "Tomato_Leaf_Mold",

    "B5":
        "Tomato_Mosaic_Virus",

    "B4":
        "Tomato_Yellow_Virus",

    "B3":
        "Tomato_Septoria_Leaf_Spot",

    "B2":
        "Tomato_Healthy",

    "B1":
        "Tomato_Early_Blight",

    "C1":
        "Tomato_Bacterial_Spot",

    "C2":
        "Tomato_Late_Blight",

    "C3":
        "Tomato_Early_Blight",

    "C4":
        "Tomato_Leaf_Mold",

    "C5":
        "Tomato_Healthy",

    "D5":
        "Potato_Early_Blight",

    "D4":
        "Potato_Late_Blight",

    "D3":
        "Tomato_Septoria_Leaf_Spot",

    "D2":
        "Tomato_Yellow_Virus",

    "D1":
        "Tomato_Healthy",
}


# ============================================================
# HELPERS
# ============================================================


def get_observation_disease(
    observation: dict,
):
    """
    Extract disease from either:

    1. Backend-style observation:
       {
           "disease": "Tomato_Early_Blight"
       }

    or CRAI frontend-style observation:

       {
           "diseaseAI": {
               "disease": "Tomato_Early_Blight"
           }
       }

    or a frontend result:

       {
           "disease_ai": {
               "prediction": "Tomato_Early_Blight"
           }
       }
    """

    # --------------------------------------------------------
    # Direct disease field
    # --------------------------------------------------------

    disease = observation.get(
        "disease"
    )

    if disease:
        return disease

    # --------------------------------------------------------
    # Frontend camelCase structure
    # --------------------------------------------------------

    disease_ai = (
        observation.get("diseaseAI")
        or {}
    )

    disease = disease_ai.get(
        "disease"
    )

    if disease:
        return disease

    disease = disease_ai.get(
        "prediction"
    )

    if disease:
        return disease

    # --------------------------------------------------------
    # Backend snake_case structure
    # --------------------------------------------------------

    disease_ai = (
        observation.get("disease_ai")
        or {}
    )

    disease = disease_ai.get(
        "disease"
    )

    if disease:
        return disease

    disease = disease_ai.get(
        "prediction"
    )

    if disease:
        return disease

    # --------------------------------------------------------
    # Summary structure
    # --------------------------------------------------------

    summary = (
        observation.get("summary")
        or {}
    )

    return summary.get(
        "disease"
    )


def is_healthy_disease(
    disease: str | None,
):
    """
    Determine whether a prediction represents
    a healthy crop.
    """

    if not disease:
        return False

    normalized = (
        disease
        .strip()
        .lower()
        .replace(" ", "_")
    )

    healthy_values = {
        "healthy",
        "tomato_healthy",
        "potato_healthy",
        "tomato_leaf",
        "potato_leaf",
    }

    return normalized in healthy_values


# ============================================================
# GET SOURCE IMAGE FOR MISSION CELL
# ============================================================


def get_cell_image(
    region: str,
):
    """
    Resolve a real PlantDoc image for a mission cell.

    Returns:

        image_path,
        source_dataset_class
    """

    if region not in MISSION_PLAN:
        raise ValueError(
            f"Unknown mission region: {region}"
        )

    disease_class = (
        MISSION_PLAN[region]
    )

    folder_name = (
        DATASET_CLASSES.get(
            disease_class
        )
    )

    if not folder_name:
        raise ValueError(
            "No PlantDoc mapping exists "
            f"for {disease_class}"
        )

    folder = (
        PLANTDOC_DIR
        / folder_name
    )

    if not folder.exists():
        raise FileNotFoundError(
            "PlantDoc folder not found: "
            f"{folder}"
        )

    images = sorted(
        [
            path
            for path in folder.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                }
            )
        ]
    )

    if not images:
        raise FileNotFoundError(
            "No images found in: "
            f"{folder}"
        )

    # --------------------------------------------------------
    # Deterministic image selection
    # --------------------------------------------------------

    mission_regions = list(
        MISSION_PLAN.keys()
    )

    region_index = (
        mission_regions.index(region)
    )

    image = images[
        region_index % len(images)
    ]

    return (
        image,
        disease_class,
    )


# ============================================================
# ANALYZE ONE MISSION CELL
# ============================================================


def analyze_mission_cell(
    region: str,
    position: int,
    previous_observations: list | None = None,
):
    """
    Run the complete CRAI intelligence pipeline
    for one simulated drone observation.

    Pipeline:

        Mission Cell
             ↓
        Real PlantDoc image
             ↓
        Disease AI V2
             ↓
        disease + confidence
             ↓
        environmental features
             ↓
        spatial features
             ↓
        Risk AI V1
             ↓
        final CRAI result
    """

    previous_observations = (
        previous_observations
        or []
    )

    # ========================================================
    # VALIDATE REGION
    # ========================================================

    if region not in MISSION_PLAN:
        raise ValueError(
            f"Unknown mission region: {region}"
        )

    if position < 0:
        raise ValueError(
            "Mission position cannot be negative."
        )

    # ========================================================
    # SELECT REAL SOURCE IMAGE
    # ========================================================

    (
        image_path,
        source_class,
    ) = get_cell_image(
        region
    )

    # ========================================================
    # DISEASE AI V2
    # ========================================================

    disease_result = predict_image(
        image_path
    )

    predicted_disease = (
        disease_result.get(
            "prediction"
        )
    )

    if not predicted_disease:
        raise ValueError(
            "Disease AI returned no prediction."
        )

    disease_confidence_raw = (
        disease_result.get(
            "confidence",
            0,
        )
    )

    disease_confidence = (
        float(
            disease_confidence_raw
        )
        / 100.0
    )

    crop = (
        disease_result.get(
            "crop"
        )
        or "Unknown"
    )

    # ========================================================
    # SPATIAL INTELLIGENCE
    # ========================================================
    #
    # Previous observations are used to estimate
    # local disease clustering.
    #
    # This is intentionally calculated from observations,
    # not hardcoded risk values.
    # ========================================================

    infected_observations = []

    for observation in (
        previous_observations
    ):

        disease = (
            get_observation_disease(
                observation
            )
        )

        if not disease:
            continue

        if not is_healthy_disease(
            disease
        ):
            infected_observations.append(
                observation
            )

    observation_count = (
        len(previous_observations)
        + 1
    )

    # --------------------------------------------------------
    # Maximum neighborhood size
    # --------------------------------------------------------

    total_neighbor_count = min(
        8,
        len(previous_observations),
    )

    infected_neighbor_count = min(
        total_neighbor_count,
        len(
            infected_observations
        ),
    )

    # --------------------------------------------------------
    # Disease density
    # --------------------------------------------------------

    if total_neighbor_count > 0:

        disease_density = (
            infected_neighbor_count
            / total_neighbor_count
        )

    else:

        disease_density = 0.0

    cluster_density = (
        disease_density
    )

    # ========================================================
    # ENVIRONMENT
    # ========================================================
    #
    # CURRENT PROTOTYPE:
    # These values are simulated.
    #
    # FUTURE:
    # Replace these values with:
    #
    # MLX90640 thermal sensor
    # environmental sensor
    # GPS / edge device telemetry
    #
    # The Risk AI interface remains unchanged.
    # ========================================================

    temperature = round(
        28.0
        + position * 0.35,
        1,
    )

    humidity = max(
        65,
        round(
            82
            - position * 0.4
        ),
    )

    thermal_anomaly = max(
        0.0,
        round(
            temperature - 30.0,
            2,
        ),
    )

    # ========================================================
    # RISK AI
    # ========================================================

    risk_input = {

        "crop":
            crop,

        "disease":
            predicted_disease,

        "disease_confidence":
            disease_confidence,

        "temperature":
            temperature,

        "humidity":
            humidity,

        "thermal_anomaly":
            thermal_anomaly,

        "infected_neighbor_count":
            infected_neighbor_count,

        "total_neighbor_count":
            total_neighbor_count,

        "disease_density":
            disease_density,

        "cluster_density":
            cluster_density,

        "observation_count":
            observation_count,

        "growth_stage":
            "Vegetative",
    }

    risk_result = predict_risk(
        risk_input
    )

    # ========================================================
    # NORMALIZED SUMMARY
    # ========================================================

    risk_score = (
        risk_result.get(
            "risk_score"
        )
    )

    risk_level = (
        risk_result.get(
            "risk_level"
        )
    )

    # ========================================================
    # FINAL CRAI RESULT
    # ========================================================

    return {

        # ----------------------------------------------------
        # Mission identity
        # ----------------------------------------------------

        "region":
            region,

        "position":
            position,

        # ----------------------------------------------------
        # Source information
        # ----------------------------------------------------

        "source_image":
            image_path.name,

        "source_dataset_class":
            source_class,

        # ----------------------------------------------------
        # Disease AI
        # ----------------------------------------------------

        "disease_ai":
            disease_result,

        # ----------------------------------------------------
        # Risk AI
        # ----------------------------------------------------

        "risk_ai":
            risk_result,

        # ----------------------------------------------------
        # Easy frontend summary
        # ----------------------------------------------------

        "summary": {

            "crop":
                crop,

            "disease":
                predicted_disease,

            "confidence":
                disease_result.get(
                    "confidence"
                ),

            "risk_score":
                risk_score,

            "risk_level":
                risk_level,
        },

        # ----------------------------------------------------
        # Environmental data
        # ----------------------------------------------------

        "environment": {

            "temperature":
                temperature,

            "humidity":
                humidity,

            "thermal_anomaly":
                thermal_anomaly,

            "source":
                "simulated",
        },

        # ----------------------------------------------------
        # Spatial intelligence
        # ----------------------------------------------------

        "spatial": {

            "infected_neighbor_count":
                infected_neighbor_count,

            "total_neighbor_count":
                total_neighbor_count,

            "disease_density":
                round(
                    disease_density,
                    3,
                ),

            "cluster_density":
                round(
                    cluster_density,
                    3,
                ),

            "observation_count":
                observation_count,
        },

        # ----------------------------------------------------
        # Pipeline state
        # ----------------------------------------------------

        "pipeline": {

            "image":
                "captured",

            "disease_ai":
                "completed",

            "risk_ai":
                "completed",

            "environment":
                "simulated",

            "spatial":
                "calculated",
        },
    }