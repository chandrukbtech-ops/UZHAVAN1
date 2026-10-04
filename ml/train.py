import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, models, transforms
from torchvision.models import MobileNet_V3_Small_Weights


CROPS = [
    "rice", "wheat", "corn", "sugarcane", "cotton", "soybean", "mustard", "tomato", "brinjal"
]
IMAGE_SIZE = 224
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


class OrderedCropFolder(Dataset):
    def __init__(self, root: Path, transform):
        self.dataset = datasets.ImageFolder(root, transform=transform)
        self.labels = self.dataset.classes
        self.label_map = {self.dataset.class_to_idx[label]: index for index, label in enumerate(self.labels)}

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        image, label = self.dataset[index]
        return image, self.label_map[label]


def make_loaders(data_dir: Path, batch_size: int):
    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.72, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.16, contrast=0.16, saturation=0.12),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    train_data = OrderedCropFolder(data_dir / "train", train_transform)
    val_data = OrderedCropFolder(data_dir / "val", val_transform)
    if train_data.labels != val_data.labels:
        raise ValueError("Train and validation class folders must match exactly.")
    represented_crops = {label.split("--", 1)[0] for label in train_data.labels}
    unknown_crops = represented_crops - set(CROPS)
    if unknown_crops:
        raise ValueError(f"Unknown crop classes: {sorted(unknown_crops)}")
    if not train_data or not val_data:
        raise ValueError("Both train/ and val/ must contain labeled images.")
    return (
        DataLoader(train_data, batch_size=batch_size, shuffle=True, num_workers=0),
        DataLoader(val_data, batch_size=batch_size, shuffle=False, num_workers=0),
        len(train_data),
        len(val_data),
    )


def evaluate(model, loader, device):
    model.eval()
    all_predictions = []
    all_targets = []
    all_confidences = []
    all_probabilities = []
    with torch.inference_mode():
        for images, labels in loader:
            logits = model(images.to(device))
            probabilities = torch.softmax(logits, dim=1)
            confidence, predictions = probabilities.max(dim=1)
            all_predictions.extend(predictions.cpu().tolist())
            all_targets.extend(labels.tolist())
            all_confidences.extend(confidence.cpu().tolist())
            all_probabilities.extend(probabilities.cpu().tolist())
    return (
        np.asarray(all_predictions),
        np.asarray(all_targets),
        np.asarray(all_confidences),
        np.asarray(all_probabilities),
    )


def choose_threshold(predictions, targets, confidences, target_precision=0.90):
    minimum_accepted = max(5, int(len(targets) * 0.05))
    for threshold in sorted(set(confidences.tolist())):
        accepted = confidences >= threshold
        if int(accepted.sum()) < minimum_accepted:
            continue
        precision = float((predictions[accepted] == targets[accepted]).mean())
        if precision >= target_precision:
            return float(threshold), precision, int(accepted.sum())
    return 1.000001, 0.0, 0


def main():
    parser = argparse.ArgumentParser(description="Fine-tune a small crop-leaf classifier.")
    parser.add_argument("--data-dir", type=Path, default=Path("ml/data"))
    parser.add_argument("--output-dir", type=Path, default=Path("backend/models"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    args = parser.parse_args()

    torch.manual_seed(42)
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    train_loader, val_loader, train_count, val_count = make_loaders(args.data_dir, args.batch_size)
    print(f"Training on {device} with {len(train_loader.dataset.labels)} crop-condition classes.")
    weights = MobileNet_V3_Small_Weights.DEFAULT
    model = models.mobilenet_v3_small(weights=weights)
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    for layer in model.features[-2:]:
        for parameter in layer.parameters():
            parameter.requires_grad = True
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(train_loader.dataset.labels))
    model.to(device)

    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=args.learning_rate,
    )
    loss_function = nn.CrossEntropyLoss()
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(images), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * labels.size(0)
        print(f"epoch {epoch + 1}/{args.epochs} - loss {total_loss / train_count:.4f}")

    predictions, targets, _, probabilities = evaluate(model, val_loader, device)
    labels = train_loader.dataset.labels
    crop_names = list(dict.fromkeys(label.split("--", 1)[0] for label in labels))
    crop_probabilities = np.column_stack([
        probabilities[:, [index for index, label in enumerate(labels) if label.split("--", 1)[0] == crop]].sum(axis=1)
        for crop in crop_names
    ])
    crop_predictions = crop_probabilities.argmax(axis=1)
    actual_crops = np.asarray([labels[int(index)].split("--", 1)[0] for index in targets])
    crop_targets = np.asarray([crop_names.index(crop) for crop in actual_crops])
    crop_confidences = crop_probabilities.max(axis=1)
    threshold, accepted_precision, accepted_count = choose_threshold(
        crop_predictions, crop_targets, crop_confidences
    )
    confusion = np.zeros((len(labels), len(labels)), dtype=int)
    for actual, predicted in zip(targets, predictions):
        confusion[actual, predicted] += 1
    per_class = {}
    for index, crop in enumerate(labels):
        true_positive = int(confusion[index, index])
        predicted_count = int(confusion[:, index].sum())
        actual_count = int(confusion[index, :].sum())
        per_class[crop] = {
            "precision": true_positive / predicted_count if predicted_count else 0.0,
            "recall": true_positive / actual_count if actual_count else 0.0,
            "support": actual_count,
        }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.onnx.export(
        model,
        torch.zeros(1, 3, IMAGE_SIZE, IMAGE_SIZE),
        args.output_dir / "crop_classifier.onnx",
        input_names=["leaf_image"],
        output_names=["crop_logits"],
        dynamic_axes={"leaf_image": {0: "batch"}, "crop_logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    accuracy = float((predictions == targets).mean())
    crop_accuracy = float((crop_predictions == crop_targets).mean())
    metadata = {
        "architecture": "MobileNetV3-Small",
        "labels": labels,
        "supported_crops": crop_names,
        "input_size": IMAGE_SIZE,
        "normalization": {"mean": MEAN, "std": STD},
        "confidence_threshold": threshold,
        "validation_accuracy": accuracy,
        "crop_validation_accuracy": crop_accuracy,
        "accepted_validation_precision": accepted_precision,
        "accepted_validation_count": accepted_count,
        "train_image_count": train_count,
        "validation_image_count": val_count,
        "per_disease_class": per_class,
        "confusion_matrix": confusion.tolist(),
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in (
        "validation_accuracy", "confidence_threshold", "accepted_validation_precision", "accepted_validation_count", "per_disease_class"
    )}, indent=2))
    if accepted_count == 0:
        print("Warning: validation did not support a threshold meeting 90% precision; the API will abstain.")


if __name__ == "__main__":
    main()