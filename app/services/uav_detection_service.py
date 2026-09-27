from pathlib import Path
from typing import Any

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    YOLO = None
    ULTRALYTICS_AVAILABLE = False


# ============================================================
# CRAI UAV DETECTION SERVICE
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "crai_uav_yolov8n_best.pt"
)

MODEL_NAME = "CRAI UAV YOLOv8n"
MODEL_VERSION = "UAV_V1"


# ============================================================
# MODEL
# ============================================================

model = None

if ULTRALYTICS_AVAILABLE and MODEL_PATH.exists():
    model = YOLO(str(MODEL_PATH))


# ============================================================
# CLASS NAMES
# ============================================================

CLASS_NAMES = {
    0: "leaves",
    1: "tomato",
}


# ============================================================
# DETECTION
# ============================================================

def detect_uav(
    image_path: str | Path,
    confidence_threshold: float = 0.25,
) -> dict[str, Any]:

    image_path = Path(
        image_path
    )

    if not ULTRALYTICS_AVAILABLE:
        raise RuntimeError(
            "Ultralytics is not installed. Install the backend requirements before using UAV inference."
        )

    if model is None:
        raise RuntimeError(
            f"UAV model not found: {MODEL_PATH}"
        )

    if not image_path.exists():
        raise FileNotFoundError(
            f"UAV image not found: {image_path}"
        )

    results = model.predict(
        source=str(image_path),
        conf=confidence_threshold,
        verbose=False,
    )

    if not results:
        return {
            "source": "UAV",
            "model": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "model_status": "READY",
            "inference_status": "NO_DETECTIONS",
            "evidence_available": False,
            "usable_for_current_decision": False,
            "evidence_scope": "NOT_AVAILABLE",
            "detections": [],
            "summary": {
                "tomato_count": 0,
                "leaf_count": 0,
                "total_detections": 0,
            },
        }

    result = results[0]

    detections = []

    tomato_count = 0
    leaf_count = 0

    confidences = []

    if result.boxes is not None:

        boxes = result.boxes

        for i in range(
            len(boxes)
        ):

            cls_id = int(
                boxes.cls[i].item()
            )

            confidence = float(
                boxes.conf[i].item()
            )

            xyxy = [
                round(
                    float(v),
                    2,
                )
                for v in boxes.xyxy[i].tolist()
            ]

            class_name = CLASS_NAMES.get(
                cls_id,
                f"class_{cls_id}",
            )

            if class_name == "tomato":
                tomato_count += 1

            elif class_name == "leaves":
                leaf_count += 1

            confidences.append(
                confidence
            )

            detections.append(
                {
                    "class_id": cls_id,
                    "class": class_name,
                    "confidence": round(
                        confidence,
                        4,
                    ),
                    "bbox": xyxy,
                }
            )

    mean_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    # --------------------------------------------------------
    # Structured spatial evidence
    # --------------------------------------------------------

    usable = bool(detections) and mean_confidence >= confidence_threshold

    return {

        "source": "UAV",

        "model": MODEL_NAME,

        "model_status": "READY",

        "inference_status": "DETECTIONS_AVAILABLE" if detections else "NO_DETECTIONS",

        "model_version": MODEL_VERSION,

        "evidence_available": bool(detections),

        "usable_for_current_decision": usable,

        "evidence_scope": "CURRENT_CANDIDATE" if usable else "INSUFFICIENT_DETECTION",

        "summary": {

            "tomato_count": tomato_count,

            "leaf_count": leaf_count,

            "total_detections": len(
                detections
            ),

            "mean_detection_confidence": round(
                mean_confidence,
                4,
            ),
        },

        "detections": detections,
    }


# ============================================================
# MODEL INFORMATION
# ============================================================

def get_uav_model_info():

    return {

        "model": MODEL_NAME,

        "version": MODEL_VERSION,

        "model_path": str(
            MODEL_PATH
        ),

        "classes": CLASS_NAMES,

        "status": "ready" if model is not None else "dependency_or_model_unavailable",
        "inference_available": model is not None,
        "dependency_available": ULTRALYTICS_AVAILABLE,
    }