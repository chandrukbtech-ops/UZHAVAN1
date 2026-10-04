# Training image layout

Run `python ml/prepare_data.py` to download and prepare the public datasets used by
the crop-identification model. It caps the sample count per source/crop, resizes
images to reduce disk use, records the source and declared license in
`dataset_manifest.json`, and removes each downloaded archive after processing.
Use `--keep-archives` only when sufficient disk space is available. All contents
under this directory are excluded from Git.

```text
ml/data/
  train/ (nine crop-name folders)
  val/   (the same nine crop folders)
```

The first version uses images labeled with crop and disease names. Disease labels
are collapsed to their crop name; this trains crop identification, not disease
diagnosis. The sources do not include mustard and brinjal in the same collection,
so the preparation script merges separate CC0 sources for those crops. Results from
these public images may not represent local field conditions.