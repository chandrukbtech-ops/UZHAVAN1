# Model artifacts

`crop_classifier.onnx` and `metadata.json` are checked in so the app can run
without downloading training images or training a model. The API loads both
files from this directory by default. Set `MODEL_DIR` to use a mounted model
folder.

To retrain the crop classifier, install `ml/requirements.txt`, prepare the
separately sourced datasets as described in `ml/data/README.md`, then run
`python ml/train.py --data-dir ml/data --output-dir backend/models`. Training
replaces the checked-in artifacts and is not part of ordinary application setup.