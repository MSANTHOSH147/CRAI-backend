from pathlib import Path
import shutil

# ---------------------------------------------------------
# CRAI - PlantVillage Dataset Preparation
# ---------------------------------------------------------

SOURCE = Path(
    r"C:\Users\91807\Downloads\PlantVillage-Dataset-master\raw\color"
)

DESTINATION = Path(
    "data/datasets/plantvillage"
)

CLASSES = {
    # Tomato
    "Tomato___healthy": "Tomato_Healthy",
    "Tomato___Early_blight": "Tomato_Early_Blight",
    "Tomato___Late_blight": "Tomato_Late_Blight",
    "Tomato___Bacterial_spot": "Tomato_Bacterial_Spot",

    # Potato
    "Potato___healthy": "Potato_Healthy",
    "Potato___Early_blight": "Potato_Early_Blight",
    "Potato___Late_blight": "Potato_Late_Blight",
}


def main():
    print("=" * 70)
    print("CRAI - PlantVillage Preparation")
    print("=" * 70)

    if not SOURCE.exists():
        print("\nERROR: PlantVillage source folder not found:")
        print(SOURCE)
        return

    DESTINATION.mkdir(
        parents=True,
        exist_ok=True
    )

    total_images = 0

    for source_class, destination_class in CLASSES.items():

        source_folder = SOURCE / source_class
        destination_folder = DESTINATION / destination_class

        print(f"\nProcessing: {source_class}")

        if not source_folder.exists():
            print("  WARNING: Source class not found")
            continue

        destination_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        images = list(source_folder.glob("*.jpg"))

        print(f"  Images found: {len(images)}")

        for image in images:
            destination = destination_folder / image.name

            shutil.copy2(
                image,
                destination
            )

        print(f"  Copied to: {destination_folder}")

        total_images += len(images)

    print("\n" + "=" * 70)
    print("PLANTVILLAGE PREPARATION COMPLETE")
    print("=" * 70)

    print(f"\nTotal images copied: {total_images}")

    print("\nDataset location:")
    print(DESTINATION)

    print("\nClasses:")

    for destination_class in CLASSES.values():
        folder = DESTINATION / destination_class

        if folder.exists():
            count = len(list(folder.glob("*.jpg")))
            print(f"  {destination_class:<30} {count}")


if __name__ == "__main__":
    main()