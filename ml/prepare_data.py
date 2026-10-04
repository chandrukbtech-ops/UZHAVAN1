import argparse
import hashlib
import json
import os
import random
import re
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
KAGGLE_CACHE_DIR = Path.home() / ".cache" / "kagglehub" / "datasets"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CROP_ORDER = [
    "rice", "wheat", "corn", "sugarcane", "cotton", "soybean", "mustard", "tomato", "brinjal"
]
CROP_ALIASES = {
    "rice": "rice",
    "wheat": "wheat",
    "corn": "corn",
    "maize": "corn",
    "sugarcane": "sugarcane",
    "cotton": "cotton",
    "soybean": "soybean",
    "soyabean": "soybean",
    "mustard": "mustard",
    "tomato": "tomato",
    "brinjal": "brinjal",
    "eggplant": "brinjal",
}
SOURCES = [
    {
        "ref": "sadiqulislamshakib/agroleaf-ai-v3",
        "license": "MIT (as declared by Kaggle dataset publisher)",
        "crops": ["corn", "cotton", "rice", "soybean", "sugarcane", "tomato", "wheat"],
    },
    {
        "ref": "ziya07/solanaceae-family-leaves-dataset",
        "license": "CC0-1.0",
        "crops": ["tomato", "brinjal"],
    },
    {
        "ref": "soumishow/alternaria-leaf-spot-of-mustard",
        "license": "CC0-1.0",
        "crops": ["mustard"],
        "crop_hint": "mustard",
        "condition_hint": "alternaria-leaf-spot",
    },
]


def crop_for_path(name: str) -> str | None:
    for part in PurePosixPath(name).parts:
        normalized = re.sub(r"[^a-z]", "", part.lower())
        for alias, crop in CROP_ALIASES.items():
            if normalized.startswith(alias):
                return crop
    return None


def condition_for_path(name: str, crop: str, condition_hint: str | None = None) -> str:
    parts = PurePosixPath(name).parts
    aliases = [alias for alias, canonical in CROP_ALIASES.items() if canonical == crop]

    def normalize_condition(value: str) -> str:
        tokens = re.sub(r"[^a-z0-9]+", " ", value.lower()).split()
        tokens = [token for token in tokens if token not in {"plant", "crop", *aliases}]
        while tokens and tokens[0] in {"diseased", "infected", "affected", "leaf", "leaves"}:
            tokens.pop(0)
        while tokens and tokens[-1] in {"leaf", "leaves"}:
            tokens.pop()
        return "-".join(tokens) or "unknown"

    for index, part in enumerate(parts[:-1]):
        normalized = re.sub(r"[^a-z]", "", part.lower())
        for alias in aliases:
            if normalized.startswith(alias):
                suffix = part[len(alias):].strip(" _-.")
                if suffix:
                    return normalize_condition(suffix)
                next_part = parts[index + 1]
                return normalize_condition(next_part)
    return condition_hint or "unknown"


def source_group(name: str) -> str:
    stem = PurePosixPath(name).stem.lower()
    stem = re.sub(r"(?:_[0-9]+deg|_new[0-9]+deg(?:flip(?:lr|ud))?|_flip(?:lr|ud)?)$", "", stem)
    return stem


def prepare_archive_from_kagglehub(source_ref: str, archive: Path) -> bool:
    try:
        import kagglehub
    except ImportError:
        return False

    downloaded_dir = local_source_dir(source_ref)
    if downloaded_dir is None:
        try:
            downloaded_dir = Path(kagglehub.dataset_download(source_ref))
        except Exception:
            return False

    if not downloaded_dir.exists():
        return False

    if archive.exists():
        return True

    return True


def download_source(source: dict, raw_dir: Path) -> Path:
    owner, dataset = source["ref"].split("/", 1)
    archive = raw_dir / f"{owner}__{dataset}.zip"
    partial_archive = archive.with_suffix(".zip.part")
    raw_dir.mkdir(parents=True, exist_ok=True)

    local_dir = local_source_dir(source["ref"])
    if local_dir is not None:
        return local_dir

    if archive.exists() and archive.stat().st_size > 0:
        return archive

    if partial_archive.exists():
        partial_archive.unlink()

    print(f"Downloading {source['ref']} to {archive} ...", flush=True)
    try:
        url = f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{dataset}"
        request = urllib.request.Request(url, headers={"User-Agent": "UzhavanCropIdentifier/1.0"})
        with urllib.request.urlopen(request, timeout=600) as response, partial_archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if partial_archive.exists():
            os.replace(partial_archive, archive)
    except Exception:
        partial_archive.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        if prepare_archive_from_kagglehub(source["ref"], archive):
            return local_source_dir(source["ref"]) or archive
        raise
    return archive


def local_source_dir(source_ref: str) -> Path | None:
    owner, dataset = source_ref.split("/", 1)
    candidates = sorted((KAGGLE_CACHE_DIR / owner / dataset).glob("versions/*"), key=lambda path: path.name)
    for version_dir in candidates:
        for possible_root in (version_dir / "dataset_clean_final", version_dir):
            if possible_root.is_dir():
                return possible_root
    return None


def iter_archive_members(archive: zipfile.ZipFile):
    for item in archive.infolist():
        path = item.filename
        if item.is_dir() or PurePosixPath(path).suffix.lower() not in IMAGE_SUFFIXES:
            continue
        yield path


def iter_directory_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            yield path


def pick_groups_directory(root: Path, max_per_class: int, source_ref: str, source: dict):
    candidates = defaultdict(lambda: defaultdict(list))
    for path in iter_directory_files(root):
        relative = path.relative_to(root).as_posix()
        crop = crop_for_path(relative) or source.get("crop_hint")
        if crop:
            condition = condition_for_path(relative, crop, source.get("condition_hint"))
            candidates[crop][condition].append((source_group(relative), path))

    selected = defaultdict(list)
    rng = random.Random(42)
    for crop, condition_groups in candidates.items():
        for condition, items in sorted(condition_groups.items()):
            group_members = defaultdict(list)
            for group, path in items:
                group_members[group].append(path)
            groups = list(group_members.items())
            rng.shuffle(groups)
            groups = groups[:max_per_class]
            split_groups = [
                (group, paths[0], "val" if int(hashlib.sha1(f"{source_ref}:{group}".encode()).hexdigest()[:8], 16) % 10 == 0 else "train")
                for group, paths in groups
            ]
            if len(split_groups) > 1 and not any(split == "val" for _, _, split in split_groups):
                group, path, _ = split_groups[-1]
                split_groups[-1] = (group, path, "val")
            if len(split_groups) > 1 and not any(split == "train" for _, _, split in split_groups):
                group, path, _ = split_groups[0]
                split_groups[0] = (group, path, "train")
            label = f"{crop}--{condition}"
            selected[crop].extend((label, f"{source_ref}:{group}", path, split) for group, path, split in split_groups)
    return selected


def pick_groups(archive: zipfile.ZipFile, max_per_class: int, source_ref: str, source: dict):
    candidates = defaultdict(lambda: defaultdict(list))
    for path in iter_archive_members(archive):
        crop = crop_for_path(path) or source.get("crop_hint")
        if crop:
            condition = condition_for_path(path, crop, source.get("condition_hint"))
            candidates[crop][condition].append((source_group(path), path))

    selected = defaultdict(list)
    rng = random.Random(42)
    for crop, condition_groups in candidates.items():
        for condition, items in sorted(condition_groups.items()):
            group_members = defaultdict(list)
            for group, path in items:
                group_members[group].append(path)
            groups = list(group_members.items())
            rng.shuffle(groups)
            groups = groups[:max_per_class]
            split_groups = [
                (group, paths[0], "val" if int(hashlib.sha1(f"{source_ref}:{group}".encode()).hexdigest()[:8], 16) % 10 == 0 else "train")
                for group, paths in groups
            ]
            if len(split_groups) > 1 and not any(split == "val" for _, _, split in split_groups):
                group, path, _ = split_groups[-1]
                split_groups[-1] = (group, path, "val")
            if len(split_groups) > 1 and not any(split == "train" for _, _, split in split_groups):
                group, path, _ = split_groups[0]
                split_groups[0] = (group, path, "train")
            label = f"{crop}--{condition}"
            selected[crop].extend((label, f"{source_ref}:{group}", path, split) for group, path, split in split_groups)
    return selected


def save_image(archive: zipfile.ZipFile, member: str, target: Path) -> str | None:
    try:
        with archive.open(member) as encoded:
            content = encoded.read()
        digest = hashlib.sha256(content).hexdigest()
        with Image.open(archive.open(member)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="JPEG", quality=88, optimize=True)
        return digest
    except (UnidentifiedImageError, OSError, zipfile.BadZipFile):
        return None


def save_image_path(source_path: Path, target: Path) -> str | None:
    try:
        content = source_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="JPEG", quality=88, optimize=True)
        return digest
    except (UnidentifiedImageError, OSError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Download and prepare public crop-leaf image datasets.")
    parser.add_argument("--max-per-class", "--max-per-crop", dest="max_per_class", type=int, default=100)
    parser.add_argument("--keep-archives", action="store_true")
    args = parser.parse_args()
    if args.max_per_class < 2:
        parser.error("--max-per-class/--max-per-crop must be at least 2 to create train and validation examples.")

    for split_dir in (TRAIN_DIR, VAL_DIR):
        shutil.rmtree(split_dir, ignore_errors=True)
        split_dir.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    counts = {"train": defaultdict(int), "val": defaultdict(int)}
    crop_counts = {"train": defaultdict(int), "val": defaultdict(int)}
    for source in SOURCES:
        source_path = download_source(source, DATA_DIR / "raw")
        try:
            if source_path.is_dir():
                selected = pick_groups_directory(source_path, args.max_per_class, source["ref"], source)
                found = sorted(selected)
                print(f"Found source crop folders for: {', '.join(found) or 'none'}", flush=True)
                for crop, samples in selected.items():
                    for label, group, member_path, split in samples:
                        filename = hashlib.sha256(f"{group}:{member_path}".encode()).hexdigest()[:20] + ".jpg"
                        target = (VAL_DIR if split == "val" else TRAIN_DIR) / label / filename
                        (TRAIN_DIR / label).mkdir(parents=True, exist_ok=True)
                        (VAL_DIR / label).mkdir(parents=True, exist_ok=True)
                        digest = save_image_path(member_path, target)
                        if not digest:
                            continue
                        if digest in seen_hashes:
                            target.unlink(missing_ok=True)
                            continue
                        seen_hashes.add(digest)
                        counts[split][label] += 1
                        crop_counts[split][crop] += 1
            else:
                with zipfile.ZipFile(source_path) as archive:
                    selected = pick_groups(archive, args.max_per_class, source["ref"], source)
                    found = sorted(selected)
                    print(f"Found source crop folders for: {', '.join(found) or 'none'}", flush=True)
                    for crop, samples in selected.items():
                        for label, group, member, split in samples:
                            filename = hashlib.sha256(f"{group}:{member}".encode()).hexdigest()[:20] + ".jpg"
                            target = (VAL_DIR if split == "val" else TRAIN_DIR) / label / filename
                            (TRAIN_DIR / label).mkdir(parents=True, exist_ok=True)
                            (VAL_DIR / label).mkdir(parents=True, exist_ok=True)
                            digest = save_image(archive, member, target)
                            if not digest:
                                continue
                            if digest in seen_hashes:
                                target.unlink(missing_ok=True)
                                continue
                            seen_hashes.add(digest)
                            counts[split][label] += 1
                            crop_counts[split][crop] += 1
        finally:
            if not args.keep_archives and source_path.is_file():
                source_path.unlink(missing_ok=True)

    supported_crops = [
        crop for crop in CROP_ORDER
        if crop_counts["train"][crop] and crop_counts["val"][crop]
    ]
    excluded_crops = [crop for crop in CROP_ORDER if crop not in supported_crops]
    for split_dir in (TRAIN_DIR, VAL_DIR):
        if split_dir.exists():
            for class_dir in split_dir.iterdir():
                crop = class_dir.name.split("--", 1)[0]
                if class_dir.is_dir() and crop in excluded_crops:
                    shutil.rmtree(class_dir)

    manifest = {
        "task": "crop_identification",
        "max_images_per_source_class": args.max_per_class,
        "sources": SOURCES,
        "counts": {
            split: {
                label: count
                for label, count in values.items()
                if label.split("--", 1)[0] in supported_crops
            }
            for split, values in counts.items()
        },
        "crop_counts": {split: dict(values) for split, values in crop_counts.items()},
        "supported_crops": supported_crops,
        "excluded_crops": excluded_crops,
        "unique_image_hashes": len(seen_hashes),
        "note": "Folder labels preserve both crop identity and leaf condition/disease.",
    }
    (DATA_DIR / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    if not supported_crops:
        raise SystemExit("Cannot train: no crops have usable train and validation data.")


if __name__ == "__main__":
    main()