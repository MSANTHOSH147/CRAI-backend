from datasets import load_dataset

print("=" * 60)
print("CRAI - PlantVillage Dataset Downloader")
print("=" * 60)

print()
print("Downloading PlantVillage dataset...")
print("Please wait...")
print()

dataset = load_dataset("mohanty/PlantVillage")

print()
print("Dataset downloaded successfully!")
print(dataset)

print()
print("Saving dataset inside CRAI...")

dataset.save_to_disk("data/datasets/plantvillage")

print()
print("=" * 60)
print("PLANTVILLAGE DOWNLOAD COMPLETE")
print("=" * 60)
print("Saved to:")
print("backend/data/datasets/plantvillage")
