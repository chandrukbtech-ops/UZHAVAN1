th# Uzhavan Farm Assistant

Uzhavan is a mobile-first farming workspace with six areas: field dashboard, leaf
analysis, English/Tamil agriculture chat, live local weather, land-and-soil crop
shortlisting, and saved crop-care reminders.

## Run the app

Start the API:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Start the web app in another terminal:

```sh
npm install
npm run dev -- --host 0.0.0.0
```

Open the Vite URL. Camera and location require `localhost` or HTTPS and browser
permission. Weather comes from Open-Meteo. Farm profiles and reminders are saved
in local browser storage; browser notifications are best-effort while the app is
open and are not a background alarm service.

## Free demo hosting

The project includes a single-container Render Blueprint in `render.yaml`. It
builds the React frontend and serves it from FastAPI so the browser and API share
one HTTPS origin. The ONNX model and metadata are included in the deployment; the
large training dataset is not.

To deploy, first put this folder in a private GitHub repository, ensuring
`backend/models/crop_classifier.onnx` and `backend/models/metadata.json` are
included. Then connect the repository in Render and create a Blueprint from
`render.yaml`. Add `AGRI_LLM_API_KEY` as a secret in the Render service settings;
never commit it. Render's free web service may sleep when idle, causing the first
request after inactivity to take about a minute. Free usage limits can change.

## Crop and leaf analysis

The API loads `backend/models/crop_classifier.onnx` and its metadata at startup.
The active model reports the crops and crop-condition classes it actually supports;
the current model includes rice, wheat, corn, sugarcane, soybean, tomato, and
brinjal. Predictions are informational and should be confirmed before treatment.
No uploaded image is persisted by the API.

Train/rebuild the crop model with the documented image datasets:

```sh
python -m pip install -r ml/requirements.txt
python ml/prepare_data.py --max-per-crop 300
python ml/train.py --data-dir ml/data --output-dir backend/models
```

See [ml/data/README.md](ml/data/README.md) for dataset sources and limitations.
Public validation results do not guarantee performance on local field photos.

## Farm assistant

The assistant retrieves from the bilingual agronomy notes in
`backend/app/main.py`. It can answer common questions about irrigation, soil,
fertilizer, planting windows, pests, and visible crop symptoms. Tamil questions
receive Tamil answers. Browser speech recognition and speech synthesis provide
voice input/output when supported; available voices and voice gender depend on
the device and browser.

For generated, context-grounded answers, get a Gemini API key from
[Google AI Studio](https://aistudio.google.com/apikey). Gemini is the default
OpenAI-compatible provider for this project:

Set `AGRI_LLM_API_KEY` in the backend environment (or as a hosting-provider
secret) and restart the API.

The default model is `gemini-2.5-flash`. The key is sent by the backend only;
never put it in frontend code or commit it. Restart the backend after setting
or changing the key. You can verify provider use by asking a question: the
advisor status changes to generated when the provider returns an answer, and
falls back to local notes if the provider is unavailable. Provider failures are
logged by the API without exposing the key to the browser. Override
`AGRI_LLM_MODEL` and `AGRI_LLM_ENDPOINT` only when using another
OpenAI-compatible provider.

Without a provider key, the API uses the local bilingual retrieval answers. The
assistant has not been fine-tuned; fine-tuning requires a selected base model,
licensed/curated training examples, and a training environment. The optional
provider generates answers from retrieved notes and is not a substitute for
local agronomist advice.

## Field planning and reminders

Crop shortlists use the selected soil and water-access categories as simple
screening guidance. Season, district, seed availability, market, and current local
advisories still matter. Reminders support irrigation, fertilizer, scouting, and
other tasks; timing should be set from the crop stage, recent rainfall, soil test,
and local crop calendar rather than a generic schedule.# UZHAVAN1
