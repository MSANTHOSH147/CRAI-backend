import json
from pathlib import Path

import torch
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image


# ============================================================
# CRAI TOMATO SPECIALIST V3
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "crai_tomato_specialist_v3_plantdoc_adapted.pth"
)

CLASSES_PATH = (
    BASE_DIR
    / "models"
    / "tomato_classes_v3.json"
)

MODEL_NAME = "CRAI Tomato Specialist"
MODEL_VERSION = "V3_PLANTDOC_ADAPTED"


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# LOAD CLASSES
# ============================================================

if not CLASSES_PATH.exists():
    raise FileNotFoundError(
        f"Tomato classes file not found: {CLASSES_PATH}"
    )

with open(
    CLASSES_PATH,
    "r",
    encoding="utf-8",
) as f:
    CLASSES = json.load(f)


if not isinstance(CLASSES, list):
    raise ValueError(
        "tomato_classes_v3.json must contain a list."
    )


if len(CLASSES) != 8:
    raise ValueError(
        f"Expected 8 tomato classes, found {len(CLASSES)}."
    )


# ============================================================
# MODEL ARCHITECTURE
# ============================================================

model = models.mobilenet_v3_small(
    weights=None
)

model.classifier = torch.nn.Sequential(
    torch.nn.Linear(
        576,
        1024,
    ),
    torch.nn.Hardswish(),
    torch.nn.Dropout(
        p=0.2
    ),
    torch.nn.Linear(
        1024,
        len(CLASSES),
    ),
)


# ============================================================
# LOAD V3 CHECKPOINT
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Tomato Specialist V3 model not found: {MODEL_PATH}"
    )


checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
    weights_only=False,
)


# ------------------------------------------------------------
# Extract state dictionary
# ------------------------------------------------------------

if isinstance(checkpoint, dict):

    if "model_state_dict" in checkpoint:

        state_dict = checkpoint[
            "model_state_dict"
        ]

    elif "state_dict" in checkpoint:

        state_dict = checkpoint[
            "state_dict"
        ]

    else:

        state_dict = checkpoint

else:

    raise ValueError(
        "Unsupported Tomato Specialist V3 checkpoint format."
    )


# ------------------------------------------------------------
# Remove DataParallel prefix
# ------------------------------------------------------------

clean_state_dict = {}

for key, value in state_dict.items():

    if key.startswith("module."):

        key = key[len("module."):]

    clean_state_dict[key] = value


# ------------------------------------------------------------
# Load weights
# ------------------------------------------------------------

missing_keys, unexpected_keys = (
    model.load_state_dict(
        clean_state_dict,
        strict=False,
    )
)


if missing_keys:

    raise RuntimeError(
        "Tomato Specialist V3 checkpoint is missing "
        f"model parameters: {missing_keys}"
    )


# ------------------------------------------------------------
# Finalize model
# ------------------------------------------------------------

model.to(DEVICE)
model.eval()


# ============================================================
# IMAGE TRANSFORM
# ============================================================

TRANSFORM = transforms.Compose(
    [
        transforms.Resize(
            (224, 224)
        ),

        transforms.ToTensor(),

        transforms.Normalize(
            mean=[
                0.485,
                0.456,
                0.406,
            ],
            std=[
                0.229,
                0.224,
                0.225,
            ],
        ),
    ]
)


# ============================================================
# DISEASE INFORMATION
# ============================================================

DISEASE_INFO = {

    "Tomato_Bacterial_Spot": {
        "crop": "Tomato",
        "disease": "Bacterial Spot",
        "severity": "Moderate",
    },

    "Tomato_Early_Blight": {
        "crop": "Tomato",
        "disease": "Early Blight",
        "severity": "Moderate",
    },

    "Tomato_Late_Blight": {
        "crop": "Tomato",
        "disease": "Late Blight",
        "severity": "High",
    },

    "Tomato_Healthy": {
        "crop": "Tomato",
        "disease": "Healthy",
        "severity": "None",
    },

    "Tomato_Mosaic_Virus": {
        "crop": "Tomato",
        "disease": "Mosaic Virus",
        "severity": "High",
    },

    "Tomato_Yellow_Virus": {
        "crop": "Tomato",
        "disease": "Yellow Leaf Curl Virus",
        "severity": "High",
    },

    "Tomato_Leaf_Mold": {
        "crop": "Tomato",
        "disease": "Leaf Mold",
        "severity": "Moderate",
    },

    "Tomato_Septoria_Leaf_Spot": {
        "crop": "Tomato",
        "disease": "Septoria Leaf Spot",
        "severity": "Moderate",
    },
}


# ============================================================
# PREDICT IMAGE
# ============================================================

def predict_image(
    image_path: str | Path,
    top_k: int = 3,
):

    image_path = Path(
        image_path
    )

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = Image.open(
        image_path
    ).convert("RGB")

    tensor = TRANSFORM(
        image
    )

    tensor = tensor.unsqueeze(
        0
    ).to(DEVICE)

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(
            tensor
        )

        probabilities = F.softmax(
            outputs,
            dim=1,
        )

        k = min(
            top_k,
            len(CLASSES),
        )

        values, indices = torch.topk(
            probabilities,
            k,
            dim=1,
        )

    # --------------------------------------------------------
    # Primary prediction
    # --------------------------------------------------------

    predicted_index = (
        indices[0][0].item()
    )

    predicted_class = CLASSES[
        predicted_index
    ]

    confidence = (
        values[0][0].item()
        * 100.0
    )

    # --------------------------------------------------------
    # Top predictions
    # --------------------------------------------------------

    top_predictions = []

    for probability, index in zip(
        values[0],
        indices[0],
    ):

        class_name = CLASSES[
            index.item()
        ]

        top_predictions.append(
            {
                "class": class_name,
                "confidence": round(
                    probability.item() * 100.0,
                    2,
                ),
            }
        )

    # --------------------------------------------------------
    # Disease metadata
    # --------------------------------------------------------

    info = DISEASE_INFO.get(
        predicted_class,
        {
            "crop": "Tomato",
            "disease": predicted_class,
            "severity": "Unknown",
        },
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {

        "prediction": predicted_class,

        "confidence": round(
            confidence,
            2,
        ),

        "crop": "Tomato",

        "disease": info[
            "disease"
        ],

        "severity": info[
            "severity"
        ],

        "top_predictions": top_predictions,

        "model": MODEL_NAME,

        "model_version": MODEL_VERSION,
    }


# ============================================================
# MODEL INFORMATION
# ============================================================

def get_model_info():

    return {

        "model": MODEL_NAME,

        "version": MODEL_VERSION,

        "classes": len(
            CLASSES
        ),

        "class_names": CLASSES,

        "device": str(
            DEVICE
        ),

        "benchmark_status": "EXTERNAL_PLANTDOC_EVALUATED",

        "status": "ready",
    }