from pathlib import Path
import json

import joblib
import pandas as pd


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BACKEND_DIR
    / "risk_ai"
    / "models"
    / "crai_risk_model_v1.pkl"
)

CONFIG_PATH = (
    BACKEND_DIR
    / "risk_ai"
    / "models"
    / "feature_config.json"
)

METADATA_PATH = (
    BACKEND_DIR
    / "risk_ai"
    / "models"
    / "model_metadata.json"
)


# ---------------------------------------------------------
# MODEL CACHE
# ---------------------------------------------------------

_model = None
_feature_columns = None
_metadata = None


def load_model():
    """
    Load the Risk AI model and configuration once.
    """

    global _model
    global _feature_columns
    global _metadata

    if _model is None:
        _model = joblib.load(MODEL_PATH)

    if _feature_columns is None:
        with open(
            CONFIG_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            _feature_columns = json.load(file)

    if _metadata is None:
        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8-sig"
        ) as file:
            _metadata = json.load(file)

    return (
        _model,
        _feature_columns,
        _metadata
    )


# ---------------------------------------------------------
# RISK LEVEL
# ---------------------------------------------------------

def get_risk_level(score: float) -> str:

    if score < 30:
        return "LOW"

    if score < 60:
        return "MODERATE"

    if score < 80:
        return "HIGH"

    return "CRITICAL"


# ---------------------------------------------------------
# DISEASE MAPPING
# ---------------------------------------------------------

DISEASE_MAP = {

    "Potato_Early_Blight":
        "disease_0_Potato_Early_Blight",

    "Potato_Late_Blight":
        "disease_1_Potato_Late_Blight",

    "Potato_Healthy":
        "disease_2_Potato_Healthy",

    "Tomato_Bacterial_Spot":
        "disease_3_Tomato_Bacterial_Spot",

    "Tomato_Early_Blight":
        "disease_4_Tomato_Early_Blight",

    "Tomato_Late_Blight":
        "disease_5_Tomato_Late_Blight",

    "Tomato_Healthy":
        "disease_6_Tomato_Healthy",

    "Tomato_Mosaic_Virus":
        "disease_7_Tomato_Mosaic_Virus",

    "Tomato_Yellow_Virus":
        "disease_8_Tomato_Yellow_Virus",

    "Tomato_Leaf_Mold":
        "disease_9_Tomato_Leaf_Mold",

    "Tomato_Septoria_Leaf_Spot":
        "disease_10_Tomato_Septoria_Leaf_Spot",
}


# ---------------------------------------------------------
# FEATURE BUILDER
# ---------------------------------------------------------

def build_features(data: dict) -> pd.DataFrame:

    disease = data.get(
        "disease",
        "Tomato_Healthy"
    )

    crop = data.get(
        "crop",
        "Tomato"
    )

    growth_stage = data.get(
        "growth_stage",
        "Vegetative"
    )

    row = {
        "disease_confidence": float(
            data.get(
                "disease_confidence",
                0.0
            )
        ),

        "temperature": float(
            data.get(
                "temperature",
                0.0
            )
        ),

        "humidity": float(
            data.get(
                "humidity",
                0.0
            )
        ),

        "thermal_anomaly": float(
            data.get(
                "thermal_anomaly",
                0.0
            )
        ),

        "infected_neighbor_count": int(
            data.get(
                "infected_neighbor_count",
                0
            )
        ),

        "total_neighbor_count": int(
            data.get(
                "total_neighbor_count",
                0
            )
        ),

        "disease_density": float(
            data.get(
                "disease_density",
                0.0
            )
        ),

        "cluster_density": float(
            data.get(
                "cluster_density",
                0.0
            )
        ),

        "observation_count": int(
            data.get(
                "observation_count",
                1
            )
        ),
    }

    # -----------------------------------------------------
    # CROP
    # -----------------------------------------------------

    row["crop_Potato"] = (
        1 if crop == "Potato" else 0
    )

    row["crop_Tomato"] = (
        1 if crop == "Tomato" else 0
    )

    # -----------------------------------------------------
    # DISEASE
    # -----------------------------------------------------

    for feature_name in DISEASE_MAP.values():

        row[feature_name] = 0

    disease_feature = DISEASE_MAP.get(
        disease
    )

    if disease_feature:
        row[disease_feature] = 1

    # -----------------------------------------------------
    # GROWTH STAGE
    # -----------------------------------------------------

    growth_features = [
        "Flowering",
        "Fruiting",
        "Mature",
        "Seedling",
        "Vegetative",
    ]

    for stage in growth_features:

        row[
            f"growth_stage_{stage}"
        ] = (
            1 if growth_stage == stage else 0
        )

    return pd.DataFrame([row])


# ---------------------------------------------------------
# PREDICTION
# ---------------------------------------------------------

def predict_risk(data: dict) -> dict:

    (
        model,
        feature_columns,
        metadata
    ) = load_model()

    features = build_features(data)

    # Force exact training feature order.
    features = features.reindex(
        columns=feature_columns,
        fill_value=0
    )

    prediction = model.predict(
        features
    )[0]

    score = float(
        max(
            0,
            min(
                100,
                prediction
            )
        )
    )

    risk_level = get_risk_level(
        score
    )

    return {
        "risk_score": round(
            score,
            2
        ),

        "risk_level": risk_level,

        "dominant_disease":
            data.get(
                "disease",
                "Unknown"
            ),

        "confidence": round(
            float(
                data.get(
                    "disease_confidence",
                    0
                )
            ),
            4
        ),

        "model": metadata.get(
            "model_name",
            "GradientBoosting"
        ),

        "version": metadata.get(
            "version",
            "v1"
        ),

        "features_used": len(
            feature_columns
        ),
    }


# ---------------------------------------------------------
# MODEL INFORMATION
# ---------------------------------------------------------

def get_model_info():

    (
        _,
        feature_columns,
        metadata
    ) = load_model()

    return {
        "model": metadata.get(
            "model_name",
            "GradientBoosting"
        ),

        "version": metadata.get(
            "version",
            "v1"
        ),

        "features": len(
            feature_columns
        ),

        "training_dataset_size":
            metadata.get(
                "training_dataset_size"
            ),

        "metrics":
            metadata.get(
                "metrics",
                {}
            ),

        "status":
            "ready",

        "disclaimer":
            metadata.get(
                "disclaimer"
            ),
    }