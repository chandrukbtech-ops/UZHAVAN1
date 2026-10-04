import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
MODEL_PATH = MODEL_DIR / "crop_classifier.onnx"
METADATA_PATH = MODEL_DIR / "metadata.json"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
INPUT_SIZE = 224
SUPPORTED_CROPS = {
    "rice", "wheat", "corn", "sugarcane", "cotton", "soybean", "mustard", "tomato", "brinjal"
}

AGRI_KNOWLEDGE = [
    {
        "id": "rice-water", "keywords": ["rice", "paddy", "nursery", "transplant", "water", "irrigation", "irrigate", "நெல்", "தண்ணீர்", "நீர்ப்பாசனம்"],
        "answer": "For a rice nursery, irrigate to keep the seedbed moist and use only shallow water after seedlings establish; avoid deep water that weakens young plants. In the main field, manage irrigation by crop stage and soil rather than keeping a fixed flood. Check the field daily during establishment and follow local agricultural guidance for the variety.",
        "ta": "நெல் நாற்றங்காலில் மண் தொடர்ந்து ஈரமாக இருக்கட்டும்; நாற்றுகள் நிலைபெற்ற பிறகு குறைந்த ஆழத்தில் மட்டும் நீர் வையுங்கள். இளம் நாற்றுகள் பலவீனமாவதைத் தவிர்க்க ஆழமான நீரைத் தவிர்க்கவும். நடவு செய்த பின் பயிர் நிலை மற்றும் மண் தன்மைக்கு ஏற்ப நீரை நிர்வகித்து, உங்கள் பகுதியில் உள்ள வேளாண் ஆலோசனையைப் பின்பற்றுங்கள்.",
    },
    {
        "id": "irrigation-method", "keywords": ["irrigation", "irrigate", "water", "drip", "sprinkler", "flood", "soil", "முறை", "நீர்ப்பாசனம்"],
        "answer": "Choose irrigation by crop and soil: drip is usually efficient for vegetables and orchards, while sprinkler systems suit many row crops where water can be applied evenly. Sandy soil needs smaller, more frequent applications; clay soil needs slower watering and good drainage. Avoid watering foliage late in the day when leaf disease is a concern.",
        "ta": "பயிர் மற்றும் மண்ணுக்கு ஏற்ற நீர்ப்பாசன முறையைத் தேர்ந்தெடுக்கவும். காய்கறி மற்றும் தோட்டப் பயிர்களுக்கு சொட்டு நீர்ப்பாசனம் நீரைச் சேமிக்க உதவும்; பல வரிசைப் பயிர்களுக்கு தெளிப்பு முறையும் பொருந்தலாம். மணற்பாங்கான மண்ணில் குறைந்த அளவு நீரை அடிக்கடி கொடுக்கவும்; களிமண் மண்ணில் மெதுவாக நீர் பாய்ச்சி வடிகால் சரியாக இருக்கச் செய்யவும்.",
    },
    {
        "id": "soil-water", "keywords": ["soil", "moisture", "dry", "drought", "mulch", "water", "மண்", "ஈரம்"],
        "answer": "Check moisture below the surface before irrigating: a dry top layer alone does not always mean the root zone is dry. Sandy soils lose water quickly; clay soils retain it longer but can become waterlogged. Mulch reduces evaporation, and drainage matters as much as irrigation after heavy rain.",
        "ta": "நீர்ப்பாசனத்திற்கு முன் மேற்பரப்பை மட்டும் அல்லாமல் வேர் பகுதியில் உள்ள ஈரத்தையும் பாருங்கள். மணற்பாங்கான மண் விரைவில் உலரும்; களிமண் மண் நீரை நீண்ட நேரம் வைத்திருக்கும், ஆனால் நீர் தேங்கும் அபாயம் உண்டு. மூடாக்கு ஆவியாதலைக் குறைக்கும்; கனமழைக்குப் பிறகு வடிகாலும் முக்கியம்.",
    },
    {
        "id": "fertilizer-basics", "keywords": ["fertilizer", "fertiliser", "urea", "nitrogen", "nutrient", "compost", "manure", "உரம்", "யூரியா"],
        "answer": "Base fertilizer decisions on a soil test and the crop’s growth stage. Split nitrogen applications reduce losses; do not apply urea onto dry soil or just before heavy rain. Keep fertilizer away from stems and follow the product label and local extension dose rather than guessing a rate.",
        "ta": "மண் பரிசோதனை மற்றும் பயிரின் வளர்ச்சி நிலையை வைத்து உரமிடுங்கள். நைட்ரஜன் உரத்தைப் பிரித்து இடுவது இழப்பைக் குறைக்கும். வறண்ட மண்ணில் அல்லது கனமழைக்கு முன் யூரியா இட வேண்டாம். உரத்தைத் தண்டிலிருந்து விலக்கி வைத்து, தயாரிப்பு லேபிள் மற்றும் உள்ளூர் வேளாண் பரிந்துரையைப் பின்பற்றுங்கள்.",
    },
    {
        "id": "pest-scouting", "keywords": ["pest", "insect", "aphid", "caterpillar", "damage", "spray", "control", "பூச்சி", "இலை"],
        "answer": "Before spraying, inspect several plants across the field and check leaf undersides and growing tips. Identify the pest and estimate how widespread the damage is; conserve beneficial insects and remove heavily affected plant parts where practical. Use only a locally approved product at its label rate, with protective equipment, and never mix products unless the label allows it.",
        "ta": "மருந்து தெளிப்பதற்கு முன் வயலின் பல இடங்களில் செடிகளைப் பார்த்து, இலை அடிப்பகுதி மற்றும் இளம் தளிர்களைச் சரிபார்க்கவும். பூச்சியை அடையாளம் கண்டு சேதம் எவ்வளவு பரவியுள்ளது என மதிப்பிடுங்கள். உங்கள் பகுதியில் அங்கீகரிக்கப்பட்ட மருந்தை லேபிள் அளவில் பாதுகாப்பு உபகரணங்களுடன் பயன்படுத்தவும்; லேபிள் அனுமதிக்காவிட்டால் மருந்துகளை கலக்க வேண்டாம்.",
    },
    {
        "id": "tomato-blight", "keywords": ["tomato", "blight", "spot", "fungus", "leaf", "humidity", "தக்காளி", "கருகல்"],
        "answer": "Tomato leaf spots and blight can look similar, so a photo and the pattern of spread help distinguish them. Remove badly affected leaves, avoid overhead watering, and improve airflow. Do not reuse the same fungicide repeatedly; confirm the diagnosis with a local extension worker before treatment.",
        "ta": "தக்காளியில் இலைப்புள்ளி மற்றும் கருகல் அறிகுறிகள் ஒன்றுபோல் தோன்றலாம்; தெளிவான படம் மற்றும் பரவும் விதம் வேறுபாட்டைக் கண்டறிய உதவும். கடுமையாகப் பாதித்த இலைகளை அகற்றி, மேலிருந்து நீர் தெளிப்பதைத் தவிர்த்து காற்றோட்டத்தை மேம்படுத்துங்கள். ஒரே பூஞ்சைக் கொல்லியை மீண்டும் மீண்டும் பயன்படுத்தாமல், சிகிச்சைக்கு முன் உள்ளூர் வேளாண் அலுவலரிடம் உறுதிப்படுத்துங்கள்.",
    },
    {
        "id": "wheat-rust", "keywords": ["wheat", "rust", "yellow", "brown", "fungal", "septoria", "கோதுமை", "துரு"],
        "answer": "Wheat rust often appears as yellow, orange, or brown powdery pustules on leaves or stems. Check whether lesions rub off and whether they are spreading through the crop. Resistant varieties and timely local disease advisories are important; confirm the disease before choosing a fungicide.",
        "ta": "கோதுமை துரு நோய் இலை அல்லது தண்டில் மஞ்சள், ஆரஞ்சு அல்லது பழுப்பு நிறத் தூள் போன்ற புள்ளிகளாகத் தோன்றலாம். புள்ளிகள் கையால் தொட்டால் உதிருகிறதா, வயலில் பரவுகிறதா என்று கவனியுங்கள். எதிர்ப்பு திறன் கொண்ட ரகங்களையும் உள்ளூர் நோய் அறிவிப்புகளையும் பயன்படுத்துங்கள்; மருந்தைத் தேர்வதற்கு முன் நோயை உறுதிப்படுத்துங்கள்.",
    },
    {
        "id": "planting-window", "keywords": ["sowing", "planting", "season", "seed", "rain", "monsoon", "when", "விதை", "பருவம்"],
        "answer": "The right sowing window depends on your district, irrigation access, variety duration, and dependable rainfall—not just the calendar month. Check the local crop calendar and avoid sowing into dry soil unless irrigation is available. Share your district, crop, and water source for a more useful schedule.",
        "ta": "சரியான விதைப்பு காலம் மாவட்டம், பாசன வசதி, ரகத்தின் வயது மற்றும் நம்பகமான மழையைப் பொறுத்தது; மாதத்தை மட்டும் வைத்து முடிவு செய்ய வேண்டாம். உள்ளூர் பயிர் காலண்டரைப் பாருங்கள். பாசனம் இல்லையெனில் உலர்ந்த மண்ணில் விதைக்க வேண்டாம். மாவட்டம், பயிர், நீர் ஆதாரம் சொன்னால் பொருத்தமான அட்டவணை கூற முடியும்.",
    },
    {
        "id": "crop-health", "keywords": ["yellow", "curl", "leaf", "healthy", "symptom", "plant", "deficiency", "இலை", "மஞ்சள்"],
        "answer": "Leaf colour or shape alone is not enough to diagnose a problem: nutrient deficiency, water stress, pests, and disease can overlap. Note which leaves are affected, how quickly symptoms spread, recent rain or spraying, and the crop stage. A clear close-up plus a whole-plant photo will improve the assessment.",
        "ta": "இலை நிறம் அல்லது வடிவத்தை மட்டும் வைத்து காரணத்தை உறுதி செய்ய முடியாது; ஊட்டச்சத்து குறைவு, நீர் அழுத்தம், பூச்சி, நோய் ஆகியவை ஒரே மாதிரி தோன்றலாம். எந்த இலைகள் பாதிக்கப்பட்டுள்ளன, அறிகுறி எவ்வளவு வேகமாகப் பரவுகிறது, சமீபத்திய மழை அல்லது தெளிப்பு, பயிர் நிலை ஆகியவற்றைக் கவனியுங்கள். நெருக்கமான படத்துடன் முழுச் செடியின் படமும் உதவும்.",
    },
    {
        "id": "mango-pruning", "keywords": ["mango", "prune", "pruning", "pruned", "branch", "canopy", "மா", "கத்தரித்தல்"],
        "answer": "For mango, start by removing dead, diseased, crossing, or inward-growing branches with clean, sharp tools. Keep pruning light and preserve an open canopy; severe pruning can reduce the next crop. Timing depends on your region and harvest cycle, so share the district and tree age before setting a schedule.",
        "ta": "மாமரத்தில் முதலில் காய்ந்த, நோயுற்ற, ஒன்றுடன் ஒன்று உரசும் அல்லது உள்நோக்கி வளரும் கிளைகளை சுத்தமான கூரிய கருவியால் அகற்றுங்கள். அளவான கத்தரிப்பைச் செய்து திறந்த கிளை அமைப்பை வைத்திருங்கள்; கடுமையான கத்தரிப்பு அடுத்த காய்ப்பைக் குறைக்கலாம். சரியான காலம் பகுதி மற்றும் அறுவடைச் சுழற்சியைப் பொறுத்தது; மாவட்டம் மற்றும் மரத்தின் வயதைச் சொல்லுங்கள்.",
    },
    {
        "id": "yield-estimate", "keywords": ["yield", "production", "harvest", "tonnes", "tons", "கிலோ", "விளைச்சல்", "மகசூல்"],
        "answer": "I can’t give a reliable yield number from the crop name alone. Yield varies with variety, district, season, planting date, soil, water, and pest pressure. Share the crop and variety, area, planting date, and current growth stage; compare estimates with your district agriculture office’s local trial data.",
        "ta": "பயிர் பெயரை மட்டும் வைத்து நம்பகமான மகசூல் எண்ணிக்கையைச் சொல்ல முடியாது. ரகம், மாவட்டம், பருவம், விதைத்த தேதி, மண், நீர் மற்றும் பூச்சித் தாக்கம் ஆகியவற்றைப் பொறுத்து மகசூல் மாறும். பயிர்/ரகம், நில அளவு, விதைத்த தேதி, தற்போதைய வளர்ச்சி நிலையைச் சொல்லுங்கள்; மாவட்ட வேளாண் அலுவலகத்தின் உள்ளூர் தரவுடன் ஒப்பிடுங்கள்.",
    },
    {
        "id": "pesticide-safety", "keywords": ["pesticide", "insecticide", "fungicide", "chemical", "thrips", "dose", "மருந்து", "திரிப்ஸ்"],
        "answer": "I shouldn’t guess a pesticide for an unidentified pest. Confirm the pest and crop, check whether treatment is needed, then use only a product registered for that crop and pest in your area, exactly as its label directs. Tell me the crop, pest signs, district, and product label if you want help understanding safe next steps.",
        "ta": "பூச்சி எது என்று உறுதி செய்யாமல் பூச்சிக்கொல்லி மருந்தை ஊகித்து பரிந்துரைக்கக் கூடாது. பயிர் மற்றும் பூச்சியை உறுதி செய்து, உங்கள் பகுதியில் அந்தப் பயிர்/பூச்சிக்கு பதிவு செய்யப்பட்ட மருந்தை லேபிள் வழிமுறையின்படி மட்டும் பயன்படுத்துங்கள். பயிர், பூச்சி அறிகுறி, மாவட்டம் மற்றும் மருந்து லேபிளைச் சொன்னால் பாதுகாப்பான அடுத்த படிகளை விளக்குகிறேன்.",
    },
]

TOPIC_KEYWORDS = {
    "irrigation": {"irrigation", "irrigate", "water", "watering", "drip", "sprinkler", "flood", "நீர்ப்பாசனம்", "தண்ணீர்", "நீர்", "பாசனம்"},
    "fertilizer": {"fertilizer", "fertiliser", "urea", "nitrogen", "nutrient", "compost", "manure", "உரம்", "யூரியா", "சத்து"},
    "pests": {"pest", "insect", "aphid", "caterpillar", "borer", "worm", "spray", "control", "துளைப்பான்", "பூச்சி", "புழு"},
    "soil": {"soil", "moisture", "dry", "drought", "mulch", "மண்", "ஈரம்"},
    "disease": {"disease", "blight", "spot", "rust", "fungus", "fungal", "curl", "yellow", "brown", "symptom", "நோய்", "கருகல்", "துரு", "மஞ்சள்", "புள்ளி"},
    "planting": {"sowing", "planting", "season", "seed", "rain", "monsoon", "when", "விதை", "பருவம்"},
    "market": {"market", "price", "cost", "sell", "mandi", "விலை", "சந்தை"},
    "pruning": {"prune", "pruning", "branch", "canopy", "கத்தரித்தல்"},
    "yield": {"yield", "production", "harvest", "tonnes", "tons", "விளைச்சல்", "மகசூல்"},
    "pesticide": {"pesticide", "insecticide", "fungicide", "chemical", "thrips", "dose", "மருந்து", "திரிப்ஸ்"},
}

ENTRY_TOPICS = {
    "rice-water": "irrigation",
    "irrigation-method": "irrigation",
    "soil-water": "soil",
    "fertilizer-basics": "fertilizer",
    "pest-scouting": "pests",
    "tomato-blight": "disease",
    "wheat-rust": "disease",
    "planting-window": "planting",
    "crop-health": "disease",
    "mango-pruning": "pruning",
    "yield-estimate": "yield",
    "pesticide-safety": "pesticide",
}

CROP_ALIASES = {
    "rice": {"rice", "paddy", "நெல்"},
    "wheat": {"wheat", "கோதுமை"},
    "corn": {"corn", "maize", "மக்காச்சோளம்"},
    "sugarcane": {"sugarcane", "கரும்பு"},
    "cotton": {"cotton", "பருத்தி"},
    "soybean": {"soybean", "சோயாபீன்"},
    "mustard": {"mustard", "கடுகு"},
    "tomato": {"tomato", "தக்காளி"},
    "brinjal": {"brinjal", "eggplant", "கத்தரிக்காய்"},
    "mango": {"mango", "மாம்பழம்", "மாமரம்", "மா"},
}


class AgriChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgriChatRequest(BaseModel):
    question: str
    language: str = "en"
    history: list[AgriChatTurn] = Field(default_factory=list)


app = FastAPI(title="Uzhavan Crop Identifier", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_session: Any = None
_input_name: str | None = None
_labels: list[str] = []
_confidence_threshold = 1.01
_model_error = "Trained model files were not found."


def preprocess_image(source: Image.Image) -> Image.Image:
    source = ImageOps.exif_transpose(source).convert("RGB")
    if source.width <= source.height:
        resized_size = (INPUT_SIZE + 32, int((INPUT_SIZE + 32) * source.height / source.width))
    else:
        resized_size = (int((INPUT_SIZE + 32) * source.width / source.height), INPUT_SIZE + 32)
    resized = source.resize(resized_size, Image.Resampling.BILINEAR)
    left = round((resized.width - INPUT_SIZE) / 2)
    top = round((resized.height - INPUT_SIZE) / 2)
    return resized.crop((left, top, left + INPUT_SIZE, top + INPUT_SIZE))


def load_model() -> bool:
    global _session, _input_name, _labels, _confidence_threshold, _model_error

    _session = None
    _input_name = None
    _labels = []
    if not MODEL_PATH.is_file() or not METADATA_PATH.is_file():
        _model_error = "Trained model files were not found."
        return False

    try:
        import onnxruntime as ort

        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        labels = metadata.get("labels")
        threshold = metadata.get("confidence_threshold")
        if not isinstance(labels, list) or not labels:
            raise ValueError("Model metadata does not contain class labels.")
        model_crops = {label.split("--", 1)[0] for label in labels}
        if not model_crops or not model_crops <= SUPPORTED_CROPS:
            raise ValueError("Model labels contain no supported crops or include unknown crops.")
        if not isinstance(threshold, (float, int)) or not 0 <= threshold <= 1.00001:
            raise ValueError("Model metadata is missing a calibrated confidence threshold.")

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, int(os.getenv("ONNX_THREADS", "2")))
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(MODEL_PATH), sess_options=options, providers=["CPUExecutionProvider"]
        )
        _session = session
        _input_name = session.get_inputs()[0].name
        _labels = labels
        _confidence_threshold = float(threshold)
        _model_error = ""
        return True
    except Exception as exc:
        _model_error = f"Could not load the trained model: {exc}"
        return False


load_model()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_ready": _session is not None,
        "supported_crops": sorted({label.split("--", 1)[0] for label in _labels}) if _session is not None else [],
        "detail": _model_error,
        "assistant_mode": "generated" if os.getenv("AGRI_LLM_API_KEY") else "local_notes",
    }


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("/", " ").split())


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z]+|[\u0b80-\u0bff]+", _normalize_text(value))
    normalized_words = set(words)
    tamil_suffixes = ("களுக்கு", "த்திலிருந்து", "யினால்", "யை", "க்கு", "இல்", "ஆல்", "உடன்", "கள்", "இன்")
    for word in words:
        if any("\u0b80" <= character <= "\u0bff" for character in word):
            for suffix in tamil_suffixes:
                if word.endswith(suffix) and len(word) > len(suffix) + 1:
                    normalized_words.add(word[:-len(suffix)])
                    break
    return normalized_words


def _find_crop(tokens: set[str]) -> str | None:
    matches = [crop for crop, aliases in CROP_ALIASES.items() if tokens.intersection(aliases)]
    return matches[0] if len(matches) == 1 else None


def _generate_grounded_answer(
    question: str,
    language: str,
    context: str,
    history: list[AgriChatTurn] | None = None,
) -> str | None:
    api_key = os.getenv("AGRI_LLM_API_KEY")
    if not api_key:
        return None

    endpoint = os.getenv(
        "AGRI_LLM_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    )
    model = os.getenv("AGRI_LLM_MODEL", "gemini-2.5-flash")
    language_name = "Tamil" if language == "ta" else "English"
    request_payload = {
        "model": model,
        "temperature": 0.45,
        "max_tokens": 280,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Uzhavan, a careful agricultural field advisor. Answer naturally and specifically in "
                    f"{language_name}. Use the retrieved notes as guidance, not as a script. Explain practical next steps, "
                    "ask for missing crop/stage/location details when needed, and never invent pesticide doses, diagnoses, "
                    "or weather. If uncertain, say what information is needed and recommend local agricultural extension advice. "
                    "Keep the answer concise, warm, and non-repetitive."
                ),
            },
        ],
    }
    request_payload["messages"].extend([
        {"role": turn.role, "content": turn.content[:2000]}
        for turn in (history or [])[-8:]
    ])
    request_payload["messages"].append({
        "role": "user",
        "content": f"Retrieved farming notes:\n{context}\n\nFarmer question:\n{question}",
    })
    payload = json.dumps(request_payload).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=18) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("The LLM provider returned an empty answer.")
        return answer.strip()
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            provider_message = error_body.get("error", {}).get("message", "")
            if not isinstance(provider_message, str):
                provider_message = ""
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            provider_message = ""
        provider_message = provider_message.replace(api_key, "[redacted]")[:300]
        logger.warning(
            "Agronomy LLM request rejected by provider (HTTP %s): %s",
            exc.code,
            provider_message or exc.reason,
        )
        return None
    except (OSError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Agronomy LLM request failed; using local guidance (%s).", type(exc).__name__)
        return None


def _retrieve_farm_answer(
    question: str,
    language: str = "en",
    history: list[AgriChatTurn] | None = None,
) -> dict[str, Any]:
    tokens = _tokens(question)
    requested_crop = _find_crop(tokens)
    requested_topics = {
        topic for topic, keywords in TOPIC_KEYWORDS.items()
        if tokens.intersection(keywords)
    }
    scored_matches: list[tuple[float, dict[str, Any]]] = []

    for item in AGRI_KNOWLEDGE:
        item_id = item["id"]
        item_crop = item_id.split("-", 1)[0] if item_id.split("-", 1)[0] in CROP_ALIASES else None
        item_topic = ENTRY_TOPICS[item_id]
        if requested_crop and item_crop and item_crop != requested_crop:
            continue
        if requested_topics and item_topic not in requested_topics:
            continue

        score = float(len(tokens.intersection(item["keywords"])))
        if item_crop and requested_crop == item_crop:
            score += 1.5
        if item_topic in requested_topics:
            score += 1.0
        if score > 0:
            scored_matches.append((score, item))

    if scored_matches:
        scored_matches.sort(key=lambda entry: entry[0], reverse=True)
        best_score, best_match = scored_matches[0]
        answer = best_match["ta"] if language == "ta" else best_match["answer"]
        source = best_match["id"]
        confidence = min(0.95, best_score / max(1, min(len(tokens), 3)))
        retrieved_context = answer
        if len(scored_matches) > 1 and scored_matches[1][0] >= best_score * 0.75:
            second = scored_matches[1][1]
            secondary_answer = second["ta"] if language == "ta" else second["answer"]
            answer = f"{answer}\n\nAlso relevant: {secondary_answer}" if language != "ta" else f"{answer}\n\nமேலும்: {secondary_answer}"
            retrieved_context = f"{retrieved_context}\n\n{secondary_answer}"
        generated_answer = _generate_grounded_answer(question, language, retrieved_context, history)
        if generated_answer:
            answer = generated_answer
            assistant_mode = "generated"
        else:
            assistant_mode = "local_notes"
    else:
        context = (
            "No direct local note matched. Do not invent time-sensitive prices, pesticide choices, rates, or diagnoses. "
            "Answer general agronomy questions cautiously and ask for the crop, district, and stage when useful."
        )
        generated_answer = _generate_grounded_answer(question, language, context, history)
        if generated_answer:
            answer = generated_answer
            assistant_mode = "generated"
        elif "market" in requested_topics:
            assistant_mode = "local_notes"
            answer = (
                f"இன்றைய சந்தை விலையை நேரடியாகப் பெறும் வசதி என்னிடம் இல்லை. நீங்கள் கேட்டது: {question} உங்கள் மாவட்டம் மற்றும் சந்தைப் பெயரைச் சொல்லுங்கள்; சரியான விலைக்கு உள்ளூர் சந்தை வாரியம் அல்லது உழவர் சந்தை அறிவிப்பைப் பார்க்கவும்."
                if language == "ta"
                else f"I don’t have a live mandi-price feed, so I can’t verify today’s rate. You asked: {question} Share your district and market; check the local mandi board for the current price."
            )
        elif "yield" in requested_topics:
            assistant_mode = "local_notes"
            answer = (
                f"நம்பகமான மகசூல் கணக்கிட கூடுதல் தகவல் தேவை. நீங்கள் கேட்டது: {question} ரகம், மாவட்டம், பரப்பளவு, விதைத்த தேதி மற்றும் பயிர் நிலையைச் சொல்லுங்கள்."
                if language == "ta"
                else f"I can’t estimate yield from that alone. You asked: {question} Share the variety, district, area, planting date, and crop stage so I can narrow down the factors."
            )
        else:
            assistant_mode = "local_notes"
            answer = (
                f"இந்தக் கேள்விக்கான உறுதிப்படுத்தப்பட்ட வழிகாட்டல் எனது உள்ளூர் குறிப்புகளில் இல்லை: {question} பயிர், வளர்ச்சி நிலை, மாவட்டம் மற்றும் நீங்கள் கவனித்ததைச் சொல்லுங்கள்; தவறான மருந்து அல்லது அளவை ஊகித்து கூறமாட்டேன்."
                if language == "ta"
                else f"I don’t have verified local guidance for this yet: {question} Tell me the crop, growth stage, district, and what you observed; I won’t guess a treatment or dose."
            )
        source = "general-agronomy"
        confidence = 0.2

    voice_text = answer.replace("  ", " ").strip()
    return {
        "answer": answer,
        "voice_text": voice_text,
        "source": source,
        "confidence": round(confidence, 2),
        "assistant_mode": assistant_mode,
    }


@app.post("/api/agri-chat")
def agri_chat(payload: AgriChatRequest) -> dict[str, Any]:
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please ask a farming question.")

    language = "ta" if payload.language.lower().startswith("ta") or any("\u0b80" <= char <= "\u0bff" for char in question) else "en"
    result = _retrieve_farm_answer(question, language, payload.history)
    return {
        "status": "ok",
        "question": question,
        **result,
    }


@app.post("/api/predict")
async def predict(image: UploadFile = File(...)) -> dict[str, Any]:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

    if _session is None or _input_name is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_NOT_READY", "message": _model_error},
        )

    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 12 MB or smaller.")

    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="Image dimensions are too large.")
            if source.width < 32 or source.height < 32:
                raise HTTPException(status_code=400, detail="Image is too small to identify.")
            image_rgb = preprocess_image(source)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a readable image.") from exc

    pixels = np.asarray(image_rgb, dtype=np.float32) / 255.0
    pixels = (pixels - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )
    tensor = np.transpose(pixels, (2, 0, 1))[None, ...]
    logits = _session.run(None, {_input_name: tensor})[0][0]
    scores = np.exp(logits - np.max(logits))
    probabilities = scores / scores.sum()
    crop_indices: dict[str, list[int]] = {}
    for index, label in enumerate(_labels):
        crop_indices.setdefault(label.split("--", 1)[0], []).append(index)
    crop_probabilities = {
        crop: float(probabilities[indices].sum())
        for crop, indices in crop_indices.items()
    }
    crop, confidence = max(crop_probabilities.items(), key=lambda item: item[1])

    if confidence < _confidence_threshold:
        return {"status": "not_sure", "crop": None, "condition": None, "disease": None, "confidence": confidence}

    condition_index = max(crop_indices[crop], key=lambda index: probabilities[index])
    _, condition = _labels[condition_index].split("--", 1)
    healthy_conditions = {"healthy", "healthy-leaf", "normal", "no-disease"}
    disease = None if condition in healthy_conditions else condition.replace("-", " ")
    return {
        "status": "identified",
        "crop": crop,
        "condition": condition,
        "disease": disease,
        "confidence": confidence,
    }


FRONTEND_DIR = BASE_DIR.parent / "dist"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")