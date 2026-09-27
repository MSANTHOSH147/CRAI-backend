import os
import json
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
from collections import defaultdict

# ============================================================
# CRAI - STANDARDIZED NEW MODEL EVALUATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLANTDOC_TEST = os.path.join(
    BASE_DIR,
    "data",
    "datasets",
    "plantdoc",
    "test"
)

CLASSES_PATH = os.path.join(
    BASE_DIR,
    "models",
    "classes_v2.json"
)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

# ============================================================
# CHANGE ONLY THESE TWO VALUES FOR EACH MODEL
# ============================================================

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "YOUR_MODEL.pth"
)

MODEL_ARCHITECTURE = "mobilenet_v3_small"

# Options:
# mobilenet_v3_small
# mobilenet_v3_large
# efficientnet_b0
# resnet18


# ============================================================
# PLANTDOC → CRAI CLASS MAPPING
# ============================================================

CLASS_MAP = {
    "Potato leaf early blight":
        "Potato_Early_Blight",

    "Potato leaf late blight":
        "Potato_Late_Blight",

    "Tomato Early blight leaf":
        "Tomato_Early_Blight",

    "Tomato leaf bacterial spot":
        "Tomato_Bacterial_Spot",

    "Tomato leaf late blight":
        "Tomato_Late_Blight",

    "Tomato leaf mosaic virus":
        "Tomato_Mosaic_Virus",

    "Tomato leaf yellow virus":
        "Tomato_Yellow_Virus",

    "Tomato mold leaf":
        "Tomato_Leaf_Mold",

    "Tomato Septoria leaf spot":
        "Tomato_Septoria_Leaf_Spot",
}


# ============================================================
# LOAD MODEL
# ============================================================

def create_model(architecture, num_classes):

    if architecture == "mobilenet_v3_small":

        model = models.mobilenet_v3_small(
            weights=None
        )

        in_features = (
            model.classifier[3].in_features
        )

        model.classifier[3] = nn.Linear(
            in_features,
            num_classes
        )

    elif architecture == "mobilenet_v3_large":

        model = models.mobilenet_v3_large(
            weights=None
        )

        in_features = (
            model.classifier[3].in_features
        )

        model.classifier[3] = nn.Linear(
            in_features,
            num_classes
        )

    elif architecture == "efficientnet_b0":

        model = models.efficientnet_b0(
            weights=None
        )

        in_features = (
            model.classifier[1].in_features
        )

        model.classifier[1] = nn.Linear(
            in_features,
            num_classes
        )

    elif architecture == "resnet18":

        model = models.resnet18(
            weights=None
        )

        in_features = model.fc.in_features

        model.fc = nn.Linear(
            in_features,
            num_classes
        )

    else:

        raise ValueError(
            f"Unsupported architecture: {architecture}"
        )

    return model


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("CRAI - STANDARDIZED PLANTDOC MODEL EVALUATION")
    print("=" * 65)

    print(f"Device:       {DEVICE}")
    print(f"Model:        {MODEL_PATH}")
    print(f"Architecture: {MODEL_ARCHITECTURE}")
    print(f"PlantDoc:     {PLANTDOC_TEST}")
    print()

    # --------------------------------------------------------
    # Load exact V2 class order
    # --------------------------------------------------------

    with open(
        CLASSES_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        classes = json.load(f)

    print("Class mapping:")
    for i, name in enumerate(classes):
        print(f"{i}: {name}")

    print()

    # --------------------------------------------------------
    # Check model
    # --------------------------------------------------------

    if not os.path.exists(MODEL_PATH):

        raise FileNotFoundError(
            f"\nModel not found:\n{MODEL_PATH}\n"
        )

    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    model = create_model(
        MODEL_ARCHITECTURE,
        len(classes)
    )

    # --------------------------------------------------------
    # Load checkpoint
    # --------------------------------------------------------

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=DEVICE
    )

    if (
        isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
    ):

        state_dict = (
            checkpoint["model_state_dict"]
        )

    else:

        state_dict = checkpoint

    try:

        model.load_state_dict(
            state_dict,
            strict=True
        )

    except RuntimeError as error:

        print()
        print("MODEL LOADING FAILED")
        print()
        print(error)
        print()
        print(
            "This usually means the model was "
            "trained with a different number of "
            "classes or architecture."
        )

        return

    model = model.to(DEVICE)
    model.eval()

    # --------------------------------------------------------
    # Preprocessing
    # --------------------------------------------------------

    transform = transforms.Compose([

        transforms.Resize(
            (224, 224)
        ),

        transforms.ToTensor(),

        transforms.Normalize(
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225]
        ),
    ])

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    correct = 0
    total = 0
    skipped = 0

    class_stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0
        }
    )

    confusion = defaultdict(
        lambda: defaultdict(int)
    )

    print()
    print("=" * 65)
    print("EVALUATING PLANTDOC")
    print("=" * 65)

    for plantdoc_class, crai_class in CLASS_MAP.items():

        folder = os.path.join(
            PLANTDOC_TEST,
            plantdoc_class
        )

        if not os.path.isdir(folder):

            print(
                f"WARNING: Missing: {plantdoc_class}"
            )

            continue

        images = [
            f for f in os.listdir(folder)
            if f.lower().endswith(
                (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".webp"
                )
            )
        ]

        print(
            f"{plantdoc_class}: "
            f"{len(images)} images"
        )

        for filename in images:

            image_path = os.path.join(
                folder,
                filename
            )

            try:

                image = Image.open(
                    image_path
                ).convert("RGB")

                tensor = transform(
                    image
                ).unsqueeze(0).to(DEVICE)

                with torch.no_grad():

                    output = model(
                        tensor
                    )

                    prediction = torch.argmax(
                        output,
                        dim=1
                    ).item()

                predicted_class = classes[
                    prediction
                ]

                total += 1

                class_stats[crai_class][
                    "total"
                ] += 1

                confusion[crai_class][
                    predicted_class
                ] += 1

                if predicted_class == crai_class:

                    correct += 1

                    class_stats[crai_class][
                        "correct"
                    ] += 1

            except Exception as error:

                skipped += 1

                print(
                    f"Skipped: {filename}"
                )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("RESULTS")
    print("=" * 65)

    if total > 0:

        accuracy = (
            correct / total
        ) * 100

        print(
            f"PlantDoc Accuracy: "
            f"{accuracy:.2f}%"
        )

    else:

        print(
            "No compatible images evaluated."
        )

    print()
    print("Per-class accuracy:")
    print("-" * 65)

    for class_name, stats in class_stats.items():

        if stats["total"] > 0:

            accuracy = (
                stats["correct"]
                / stats["total"]
            ) * 100

            print(
                f"{class_name:<35}"
                f"{accuracy:>6.2f}% "
                f"({stats['correct']}/"
                f"{stats['total']})"
            )

    print()
    print("Confusion Matrix:")
    print("-" * 65)

    for actual, predictions in confusion.items():

        print()
        print(
            f"Actual: {actual}"
        )

        for predicted, count in sorted(
            predictions.items()
        ):

            print(
                f"  -> {predicted}: {count}"
            )

    print()
    print("-" * 65)
    print(f"Images evaluated: {total}")
    print(f"Images skipped:   {skipped}")
    print("-" * 65)


if __name__ == "__main__":
    main()