import os
import json
import copy
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms, models


# ============================================================
# CRAI - Plant Disease Training
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data", "datasets", "plantvillage")
MODEL_DIR = os.path.join(BASE_DIR, "models")

os.makedirs(MODEL_DIR, exist_ok=True)


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

IMAGE_SIZE = 224
BATCH_SIZE = 16
EPOCHS = 5
LEARNING_RATE = 0.0005
VALIDATION_SPLIT = 0.20

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("=" * 60)
print("CRAI - Plant Disease AI Training")
print("=" * 60)

print(f"Device: {DEVICE}")
print(f"Dataset: {DATA_DIR}")
print(f"Model output: {MODEL_DIR}")
print()


# ------------------------------------------------------------
# Image preprocessing
# ------------------------------------------------------------

train_transforms = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ColorJitter(
        brightness=0.2,
        contrast=0.2,
        saturation=0.2
    ),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


val_transforms = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# ------------------------------------------------------------
# Load PlantVillage
# ------------------------------------------------------------

print("Loading PlantVillage dataset...")

full_dataset = datasets.ImageFolder(
    DATA_DIR,
    transform=train_transforms
)

class_names = full_dataset.classes

print(f"Classes found: {len(class_names)}")

for index, name in enumerate(class_names):
    print(f"  {index}: {name}")

print(f"Total images: {len(full_dataset)}")
print()


# ------------------------------------------------------------
# Train / validation split
# ------------------------------------------------------------

validation_size = int(len(full_dataset) * VALIDATION_SPLIT)
training_size = len(full_dataset) - validation_size

generator = torch.Generator().manual_seed(42)

train_dataset, val_dataset = random_split(
    full_dataset,
    [training_size, validation_size],
    generator=generator
)

# Use validation transforms for validation data
val_dataset.dataset = datasets.ImageFolder(
    DATA_DIR,
    transform=val_transforms
)

print(f"Training images:   {len(train_dataset)}")
print(f"Validation images: {len(val_dataset)}")
print()


# ------------------------------------------------------------
# DataLoaders
# ------------------------------------------------------------

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)


# ------------------------------------------------------------
# MobileNetV3-Small
# ------------------------------------------------------------

print("Creating MobileNetV3-Small...")

weights = models.MobileNet_V3_Small_Weights.DEFAULT

model = models.mobilenet_v3_small(weights=weights)

# Freeze pretrained feature extractor
for parameter in model.features.parameters():
    parameter.requires_grad = False

# Replace classifier
input_features = model.classifier[3].in_features

model.classifier[3] = nn.Linear(
    input_features,
    len(class_names)
)

model = model.to(DEVICE)

print("Model ready.")
print()


# ------------------------------------------------------------
# Loss + optimizer
# ------------------------------------------------------------

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.Adam(
    model.classifier[3].parameters(),
    lr=LEARNING_RATE
)


# ------------------------------------------------------------
# Training
# ------------------------------------------------------------

best_accuracy = 0.0
best_model_state = copy.deepcopy(model.state_dict())

print("=" * 60)
print("STARTING TRAINING")
print("=" * 60)

start_time = time.time()

for epoch in range(EPOCHS):

    print()
    print(
        f"Epoch {epoch + 1}/{EPOCHS}"
    )

    # -------------------------
    # Training
    # -------------------------

    model.train()

    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in train_loader:

        images = images.to(DEVICE)
        labels = labels.to(DEVICE)

        optimizer.zero_grad()

        outputs = model(images)

        loss = criterion(outputs, labels)

        loss.backward()

        optimizer.step()

        running_loss += loss.item() * images.size(0)

        _, predictions = torch.max(outputs, 1)

        total += labels.size(0)
        correct += (predictions == labels).sum().item()

    train_loss = running_loss / total
    train_accuracy = correct / total

    # -------------------------
    # Validation
    # -------------------------

    model.eval()

    validation_correct = 0
    validation_total = 0

    with torch.no_grad():

        for images, labels in val_loader:

            images = images.to(DEVICE)
            labels = labels.to(DEVICE)

            outputs = model(images)

            _, predictions = torch.max(outputs, 1)

            validation_total += labels.size(0)

            validation_correct += (
                predictions == labels
            ).sum().item()

    validation_accuracy = (
        validation_correct / validation_total
    )

    print(
        f"Train Loss: {train_loss:.4f}"
    )

    print(
        f"Train Accuracy: {train_accuracy * 100:.2f}%"
    )

    print(
        f"Validation Accuracy: "
        f"{validation_accuracy * 100:.2f}%"
    )

    # Save best model in memory
    if validation_accuracy > best_accuracy:

        best_accuracy = validation_accuracy

        best_model_state = copy.deepcopy(
            model.state_dict()
        )

        print("★ New best model!")


elapsed = time.time() - start_time

print()
print("=" * 60)
print("TRAINING COMPLETE")
print("=" * 60)

print(
    f"Best validation accuracy: "
    f"{best_accuracy * 100:.2f}%"
)

print(
    f"Training time: "
    f"{elapsed / 60:.1f} minutes"
)


# ------------------------------------------------------------
# Save model
# ------------------------------------------------------------

model.load_state_dict(best_model_state)

model_path = os.path.join(
    MODEL_DIR,
    "crai_disease_mobilenetv3.pth"
)

torch.save(
    {
        "model_state_dict": model.state_dict(),
        "class_names": class_names,
        "image_size": IMAGE_SIZE,
        "architecture": "mobilenet_v3_small",
        "best_validation_accuracy": best_accuracy,
    },
    model_path
)


# ------------------------------------------------------------
# Save class mapping
# ------------------------------------------------------------

classes_path = os.path.join(
    MODEL_DIR,
    "classes.json"
)

with open(
    classes_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        class_names,
        file,
        indent=4
    )


print()
print(f"Model saved:   {model_path}")
print(f"Classes saved: {classes_path}")

print()
print("CRAI AI MODEL READY.")