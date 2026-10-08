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

## Free Render deployment

`render.yaml` configures a free Docker web service with `/api/health` as its
health check. The container serves the React frontend and FastAPI backend on one
HTTPS origin. The ONNX model and metadata are included; the training dataset is
not. Render's free service may spin down after inactivity, so the first request
after a quiet period can take longer.

Create a Blueprint in Render from this GitHub repository. During setup, provide
the six `VITE_FIREBASE_*` values from your Firebase web-app configuration when
prompted; Render passes them to the Docker build so account sign-in is enabled
in the generated frontend. After Render assigns a public domain, add that domain
under Firebase Authentication → Settings → Authorized domains.

The web app and FastAPI API run on Render. To use Qwen without paying for a
separate model server, Ollama can run on your Mac and connect through a
Cloudflare Quick Tunnel. This is a demo arrangement, not reliable production
hosting: the Mac, Ollama, gateway, and tunnel must stay running and online.
Render's free service can also sleep. Quick Tunnel URLs are temporary and can
change after a restart.

On the Mac, install Cloudflare Tunnel and start Ollama:

```sh
brew install cloudflared
ollama pull qwen2.5:3b
ollama serve
```

In another terminal, start the token-protected gateway. Keep the generated token
private; enter the same value in Render's `OLLAMA_API_KEY` environment variable:

```sh
export OLLAMA_GATEWAY_TOKEN="$(openssl rand -hex 32)"
python backend/ollama_gateway.py
```

In a third terminal, create the temporary HTTPS tunnel:

```sh
cloudflared tunnel --url http://127.0.0.1:11435
```

Copy the `https://...trycloudflare.com` URL printed by the command into Render's
`OLLAMA_HOST` variable, without a path. Set `OLLAMA_API_KEY` in Render to the
same token used for `OLLAMA_GATEWAY_TOKEN` on the Mac, then redeploy. Do not
publish port 11434 directly. The gateway only accepts authenticated chat
requests and forwards them to Ollama on loopback. If the tunnel URL changes,
update `OLLAMA_HOST` in Render. When Ollama or the tunnel is unreachable, chat
falls back to the app's built-in local guidance.

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

Chat responses report `assistant_mode: "local_model"` when the configured
Ollama model generated the answer, or `"local_notes"` when the model is
unavailable and the built-in notes were used. `OLLAMA_HOST` is the Ollama
server's base URL, `OLLAMA_API_KEY` is the gateway token, and `AGRI_LLM_MODEL`
selects a model already pulled in Ollama.

## Field planning and reminders

Crop shortlists use the selected soil and water-access categories as simple
screening guidance. Season, district, seed availability, market, and current local
advisories still matter. Reminders support irrigation, fertilizer, scouting, and
other tasks; timing should be set from the crop stage, recent rainfall, soil test,
and local crop calendar rather than a generic schedule.
