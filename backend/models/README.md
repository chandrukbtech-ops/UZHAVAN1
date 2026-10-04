# Model artifacts

Run `python ml/train.py --data-dir ml/data --output-dir backend/models` to generate
`crop_classifier.onnx` and `metadata.json` here. Keep the ONNX file out of Git;
it is generated from the separately licensed training images. The API loads both
files from this directory by default. Set `MODEL_DIR` to use a mounted model folder.