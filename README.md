# Uzhavan Farm Assistant

Uzhavan is a mobile-first farming workspace with six areas: field dashboard, leaf
analysis, English/Tamil agriculture chat, live local weather, land-and-soil crop
shortlisting, and saved crop-care reminders.

## Run the app

Install and start Ollama on the same computer as the API. On macOS with
Homebrew:

```sh
brew install ollama
ollama serve
```

In another terminal, download the local chat model:

```sh
ollama pull qwen2.5:3b
```

Then start the API:

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
permission. Weather comes from Open-Meteo. Without an account, farm profiles and
reminders stay in this browser. Sign in to sync them privately with Firebase.
Browser notifications are best-effort while the app is open, not a background
alarm service.

## Firebase accounts and sync

Firebase is used only for authentication and small farm records. Uzhavan does not
upload leaf photos, chat history, or weather data to Firebase. A farm profile uses
one document and each task uses one document under that account. Signed-out data
remains in browser storage.

The Firebase web settings are read from `.env.local`; copy `.env.example` and fill
in the project values. Restart Vite after changing environment settings.
The Firebase SDK is split from the main app bundle and excluded from the offline
app-shell cache; cloud sign-in and sync need a network connection when that
chunk is not already cached by the browser.

In Firebase Console:

1. Enable **Email/Password** and **Google** under Authentication → Sign-in method.
2. Create a Cloud Firestore database.
3. Publish the included `firestore.rules`. The rules allow a user to read and
   write only documents under their own UID.
4. Add `localhost` and the production domain under Authentication → Settings →
   Authorized domains.

Firebase's browser configuration (including its API key) identifies the project,
but is not an authorization boundary. Firestore rules and enabled authentication
providers protect the data. Review Firebase's free-tier quotas in the console;
this app stores no images or large generated content.

## Railway deployment

`railway.json` configures Railway to build the single-container Dockerfile and
use `/api/health` as its deployment health check. The container serves both the
React frontend and FastAPI backend on one HTTPS origin. The ONNX model and its
metadata are included; the training dataset is not.

Connect this repository in Railway and deploy the root service. Add all six
`VITE_FIREBASE_*` values from your Firebase web-app configuration in the Railway
service variables before deploying; Railway supplies them during the Docker
build so sign-in is enabled in the generated frontend. After Railway assigns a
public domain, add that domain under Firebase Authentication → Settings →
Authorized domains.

The Qwen model is not included in the app container. Set `OLLAMA_HOST` to an
Ollama server URL reachable from Railway and make sure that server has the model
named by `AGRI_LLM_MODEL` (default `qwen2.5:3b`). Do not point this setting at
`localhost` or an unauthenticated public Ollama endpoint. Without a reachable
Ollama server, chat uses the built-in local guidance fallback; crop analysis,
farm, and task features remain available.

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

The assistant runs the open-weight `qwen2.5:3b` model locally through Ollama; it
does not require a Gemini key or send chat prompts to a cloud LLM. The model is
pre-trained, not trained by this project. Uzhavan adds its own bilingual farming
notes from `backend/app/main.py` as context to answers. Keep those notes accurate
and add reviewed local guidance there as needed. Tamil questions request Tamil
answers, though quality depends on the model. Disease precautions are shown
directly after an identified leaf condition. Advice describes possible causes
and safer prevention steps; it does
not confirm a diagnosis or prescribe pesticide doses. Browser speech
recognition and speech synthesis depend on browser/device support. The app now
prefers an installed natural-sounding voice for the selected language, but voice
quality and availability are controlled by the browser and operating system.

The API health response reports `llm_ready` and `assistant_model`. Chat responses
report `assistant_mode: "local_model"` when Ollama generated the answer, or
`"local_notes"` when Ollama is unavailable and the built-in notes were used.
Set `OLLAMA_HOST` if Ollama runs at a different address and `AGRI_LLM_MODEL` if
you have pulled a different Ollama model. For example, to use another model,
pull it with Ollama and set `AGRI_LLM_MODEL` before starting the API.

## Field planning and reminders

Crop shortlists use the selected soil and water-access categories as simple
screening guidance. Season, district, seed availability, market, and current local
advisories still matter. Reminders support irrigation, fertilizer, scouting, and
other tasks; timing should be set from the crop stage, recent rainfall, soil test,
and local crop calendar rather than a generic schedule.
