#!/usr/bin/env python3
"""
train_model.py

Train (fine-tune) a TensorFlow Keras classifier using disputed feedback.
Saves final model to models/final_model/model.h5
"""

import os
import json
import argparse
from pathlib import Path
import sys
import time
import numpy as np

# TensorFlow / Keras
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers
from tensorflow.keras.preprocessing.image import ImageDataGenerator, load_img, img_to_array

# =====================================================
# 📂 CONFIG & PATHS
# =====================================================
PROJECT_ROOT = Path(__file__).resolve().parent
RETRAIN_JSON_DEFAULT = PROJECT_ROOT / "data" / "retrain_data.json"
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
MODEL_DIR = PROJECT_ROOT / "models" / "final_model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "model.h5"

# =====================================================
# ⚙️ HYPERPARAMETERS
# =====================================================
IMG_SIZE = (224, 224)
BATCH_SIZE = 8
EPOCHS = 3
LEARNING_RATE = 1e-4


def parse_args():
    p = argparse.ArgumentParser(description="Train NSFW AI TensorFlow Model")
    p.add_argument("--data", type=str, default=str(RETRAIN_JSON_DEFAULT))
    p.add_argument("--dataset", type=str, help="Path to dataset directory with nsfw/ and safe/ subdirs")
    p.add_argument("--epochs", type=int, default=EPOCHS)
    p.add_argument("--batch", type=int, default=BATCH_SIZE)
    p.add_argument("--lr", type=float, default=LEARNING_RATE)
    p.add_argument("--img_size", type=int, nargs=2, default=list(IMG_SIZE))
    return p.parse_args()


# =====================================================
# 📄 LOAD RETRAIN DATA
# =====================================================
def load_retrain_entries(path):
    if not os.path.exists(path):
        print(f"⚠️ No retrain file found at {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    normalized = []
    for e in data:
        if not isinstance(e, dict):
            continue
        file = e.get("file") or e.get("filename") or e.get("upload") or e.get("path")
        if not file:
            continue

        # Prioritize secondary labels for auto-retrain entries
        chosen = None
        if e.get("auto_retrain") and e.get("correct_label"):
            chosen = e.get("correct_label")
        else:
            # Use feedback_type if available, otherwise fallback to chosen or other fields
            chosen = e.get("feedback_type") or e.get("chosen") or e.get("chosen_label") or e.get("label") or e.get("suggested")

        if chosen is None:
            continue

        chosen = str(chosen).lower()
        if "nsfw" in chosen or "high" in chosen:
            lbl = "nsfw"
        else:
            lbl = "safe"

        normalized.append({"file": file, "label": lbl})
    return normalized


# =====================================================
# 🧠 DATASET BUILDER
# =====================================================
def build_dataset(entries, img_size=(224, 224), batch_size=8, augment=False):
    images, labels = [], []
    for e in entries:
        p = os.path.join(UPLOADS_DIR, e["file"])
        if not os.path.exists(p):
            continue
        try:
            img = load_img(p, target_size=img_size)
            arr = img_to_array(img)
            images.append(arr)
            labels.append(1 if e["label"] == "nsfw" else 0)
        except Exception as ex:
            print("❌ Failed to load", p, ":", ex)

    if not images:
        return None

    X = np.array(images, dtype="float32") / 255.0
    y = tf.keras.utils.to_categorical(labels, num_classes=2)

    if augment:
        datagen = ImageDataGenerator(
            rotation_range=8,
            width_shift_range=0.05,
            height_shift_range=0.05,
            horizontal_flip=True,
        )
        generator = datagen.flow(X, y, batch_size=batch_size)
        return generator, len(X)
    else:
        dataset = tf.data.Dataset.from_tensor_slices((X, y)).shuffle(len(X)).batch(batch_size)
        return dataset, len(X)


# =====================================================
# 🏗️ MODEL CREATION (MobileNetV2-based)
# =====================================================
def create_model(input_shape=(224, 224, 3), lr=1e-4):
    base = tf.keras.applications.MobileNetV2(
        include_top=False, input_shape=input_shape, weights="imagenet", pooling="avg"
    )
    base.trainable = False  # Freeze the base layers
    x = base.output
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(2, activation="softmax")(x)
    model = models.Model(inputs=base.input, outputs=out)
    model.compile(optimizer=optimizers.Adam(lr), loss="categorical_crossentropy", metrics=["accuracy"])
    return model


# =====================================================
# 🚀 MAIN ENTRY POINT
# =====================================================
def build_dataset_from_dir(dataset_path, img_size=(224, 224), batch_size=8, augment=False):
    dataset_path = Path(dataset_path)
    images, labels = [], []
    for label_dir in ["nsfw", "safe"]:
        dir_path = dataset_path / label_dir
        if not dir_path.exists():
            continue
        label = 1 if label_dir == "nsfw" else 0
        for img_file in dir_path.glob("*"):
            if not img_file.is_file() or img_file.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
                continue
            try:
                img = load_img(str(img_file), target_size=img_size)
                arr = img_to_array(img)
                images.append(arr)
                labels.append(label)
            except Exception as ex:
                print("❌ Failed to load", img_file, ":", ex)

    if not images:
        return None

    X = np.array(images, dtype="float32") / 255.0
    y = tf.keras.utils.to_categorical(labels, num_classes=2)

    if augment:
        datagen = ImageDataGenerator(
            rotation_range=8,
            width_shift_range=0.05,
            height_shift_range=0.05,
            horizontal_flip=True,
        )
        generator = datagen.flow(X, y, batch_size=batch_size)
        return generator, len(X)
    else:
        dataset = tf.data.Dataset.from_tensor_slices((X, y)).shuffle(len(X)).batch(batch_size)
        return dataset, len(X)


def main():
    args = parse_args()

    if args.dataset:
        print("📘 Starting training using dataset directory:", args.dataset)
        dataset_info = build_dataset_from_dir(args.dataset, img_size=tuple(args.img_size), batch_size=args.batch, augment=False)
        if dataset_info is None:
            print("❌ No valid images found in dataset directory. Exiting.")
            sys.exit(1)
        dataset, n_samples = dataset_info
        print(f"📊 Prepared dataset with {n_samples} samples.")
    else:
        print("📘 Starting training using data:", args.data)
        entries = load_retrain_entries(args.data)
        print(f"✅ Found {len(entries)} labeled entries.")
        if not entries:
            print("⚠️ No data available for retraining. Exiting.")
            sys.exit(0)

        dataset_info = build_dataset(entries, img_size=tuple(args.img_size), batch_size=args.batch, augment=False)
        if dataset_info is None:
            print("❌ No valid images found. Exiting.")
            sys.exit(1)

        dataset, n_samples = dataset_info
        print(f"📊 Prepared dataset with {n_samples} samples.")

    # Build model
    model = create_model(input_shape=(args.img_size[0], args.img_size[1], 3), lr=args.lr)
    print("🧩 Model Summary:")
    model.summary()

    # Train
    print(f"🏁 Starting training for {args.epochs} epochs...")
    start = time.time()

    if isinstance(dataset, tf.data.Dataset):
        model.fit(dataset, epochs=args.epochs, verbose=1)
    else:
        steps = max(1, n_samples // args.batch)
        model.fit(dataset, steps_per_epoch=steps, epochs=args.epochs, verbose=1)

    duration = time.time() - start
    print(f"✅ Training completed in {duration:.1f}s.")

    # Save model and metadata
    print(f"💾 Saving model to {MODEL_PATH}")
    model.save(str(MODEL_PATH))

    meta = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": n_samples,
        "epochs": args.epochs,
        "img_size": args.img_size,
        "base_model": "MobileNetV2",
    }

    with open(MODEL_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("📄 Metadata written.")
    print("🎯 Model successfully updated as 'final_model' for live use.")
    sys.exit(0)


if __name__ == "__main__":
    main()
