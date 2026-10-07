from io import BytesIO
import json
from urllib.error import HTTPError

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image, ImageDraw
import pytest

from backend.app import main


client = TestClient(main.app)
LABELS = [
    "rice--healthy", "wheat--healthy", "corn--healthy", "sugarcane--healthy", "cotton--healthy",
    "soybean--healthy", "mustard--healthy", "tomato--healthy", "brinjal--healthy",
]


@pytest.fixture(autouse=True)
def prevent_live_ollama_requests(monkeypatch):
    def unavailable_ollama(request, timeout):
        raise ConnectionRefusedError("Ollama is not running in the test environment.")

    monkeypatch.setattr(main, "urlopen", unavailable_ollama)


class FakeSession:
    def __init__(self, logits):
        self.logits = logits

    def run(self, outputs, inputs):
        assert inputs["leaf_image"].shape == (1, 3, 224, 224)
        return [self.logits]


def jpeg_image():
    image = Image.new("RGB", (48, 48), "green")
    content = BytesIO()
    image.save(content, format="JPEG")
    return content.getvalue()


def test_health_reports_missing_model(monkeypatch):
    monkeypatch.setattr(main, "_session", None)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["model_ready"] is False


def test_health_reports_crops_in_loaded_model(monkeypatch):
    monkeypatch.setattr(main, "_session", FakeSession(np.zeros((1, 2), dtype=np.float32)))
    monkeypatch.setattr(main, "_labels", ["rice--healthy", "tomato--healthy"])

    response = client.get("/api/health")

    assert response.json()["supported_crops"] == ["rice", "tomato"]


def test_agri_chat_returns_domain_answer():
    response = client.post(
        "/api/agri-chat",
        json={"question": "How often should I irrigate rice in the nursery?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert "rice" in body["answer"].lower()
    assert "irrig" in body["answer"].lower()


def test_agri_chat_answers_tamil_question_in_tamil():
    response = client.post(
        "/api/agri-chat",
        json={"question": "நெல் பயிருக்கு தண்ணீர் எப்படி கொடுக்க வேண்டும்?"},
    )

    assert response.status_code == 200
    assert any("\u0b80" <= character <= "\u0bff" for character in response.json()["answer"])


def test_agri_chat_uses_local_ollama_without_api_key(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({
                "message": {"content": "Check the rice root-zone moisture before irrigating."},
            }).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(main, "urlopen", fake_urlopen)

    response = client.post(
        "/api/agri-chat",
        json={
            "question": "How often should I irrigate rice?",
            "history": [{"role": "user", "content": "I planted last week."}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Check the rice root-zone moisture before irrigating."
    assert body["assistant_mode"] == "local_model"
    assert captured["timeout"] == 120
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "qwen2.5:3b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert "Uzhavan farming knowledge:" in captured["payload"]["messages"][-1]["content"]


def test_agri_chat_sends_unmatched_questions_to_local_model(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({
                "message": {"content": "Salinity can reduce water uptake and delay germination."},
            }).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(main, "urlopen", fake_urlopen)
    question = "How does soil salinity affect seed germination?"
    response = client.post("/api/agri-chat", json={"question": question})

    assert response.status_code == 200
    assert response.json()["answer"] == "Salinity can reduce water uptake and delay germination."
    assert response.json()["assistant_mode"] == "local_model"
    assert question in captured["payload"]["messages"][-1]["content"]


def test_health_reports_local_model_readiness(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "qwen2.5:3b"}]}).encode()

    monkeypatch.setattr(main, "urlopen", lambda request, timeout: FakeResponse())

    response = client.get("/api/health")

    assert response.json()["assistant_provider"] == "ollama"
    assert response.json()["assistant_model"] == "qwen2.5:3b"
    assert response.json()["llm_ready"] is True
    assert response.json()["assistant_mode"] == "local_model"


def test_agri_chat_falls_back_to_local_notes_when_ollama_fails(monkeypatch):

    def fail_urlopen(request, timeout):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(main, "urlopen", fail_urlopen)

    response = client.post(
        "/api/agri-chat",
        json={"question": "How often should I irrigate rice?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["assistant_mode"] == "local_notes"
    assert body["source"] == "rice-water"


def test_disease_care_returns_structured_local_model_guidance(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({
                "message": {"content": "Possible reasons: wet leaves.\n\nPrecautions: improve airflow."},
            }).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(main, "urlopen", fake_urlopen)
    response = client.post(
        "/api/agri-chat",
        json={
            "question": "Crop: tomato. Observed disease or symptoms: yellow spots.",
            "language": "en",
            "intent": "disease_care",
        },
    )

    assert response.status_code == 200
    assert response.json()["assistant_mode"] == "local_model"
    assert "do not claim a definite diagnosis" in captured["payload"]["messages"][0]["content"].lower()
    assert "Ways to reduce further spread" in captured["payload"]["messages"][0]["content"]
    assert "Do not prescribe pesticide" in captured["payload"]["messages"][0]["content"]


def test_disease_care_has_safe_local_fallback_when_ollama_unavailable(monkeypatch):
    def fail_urlopen(request, timeout):
        raise TimeoutError("Ollama is offline")

    monkeypatch.setattr(main, "urlopen", fail_urlopen)
    response = client.post(
        "/api/agri-chat",
        json={
            "question": "Crop: tomato. Observed disease or symptoms: yellow spots.",
            "language": "en",
            "intent": "disease_care",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant_mode"] == "local_notes"
    assert body["source"] == "disease-care"
    assert "Possible reasons:" in body["answer"]
    assert "Precautions to take now:" in body["answer"]
    assert "Ways to reduce further spread:" in body["answer"]
    assert "What to do next:" in body["answer"]
    assert "Do not guess or apply pesticide products or doses." in body["answer"]


def test_agri_chat_logs_local_ollama_http_error(monkeypatch, caplog):
    def reject_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=BytesIO(json.dumps({"error": "model not found"}).encode()),
        )

    monkeypatch.setattr(main, "urlopen", reject_urlopen)

    response = client.post(
        "/api/agri-chat",
        json={"question": "How often should I irrigate rice?"},
    )

    assert response.status_code == 200
    assert response.json()["assistant_mode"] == "local_notes"
    assert "HTTP 404" in caplog.text
    assert "model not found" in caplog.text


def test_agri_chat_does_not_route_crop_fertilizer_question_to_irrigation():
    response = client.post(
        "/api/agri-chat",
        json={"question": "What fertilizer should I use for my rice crop?"},
    )

    assert response.json()["source"] == "fertilizer-basics"


def test_agri_chat_does_not_apply_rice_advice_to_sugarcane():
    response = client.post(
        "/api/agri-chat",
        json={"question": "How often should I irrigate sugarcane?"},
    )

    assert response.json()["source"] == "irrigation-method"
    assert "rice nursery" not in response.json()["answer"].lower()


def test_agri_chat_asks_for_context_instead_of_matching_price_as_rice():
    response = client.post(
        "/api/agri-chat",
        json={"question": "What is the market price for onions today?"},
    )

    assert response.json()["source"] == "general-agronomy"


def test_agri_chat_routes_tamil_stem_borer_question_to_pest_guidance():
    response = client.post(
        "/api/agri-chat",
        json={"question": "நெல் பயிரில் தண்டு துளைப்பான் பூச்சியை எப்படி கட்டுப்படுத்துவது?"},
    )

    assert response.json()["source"] == "pest-scouting"


def test_agri_chat_provides_mango_pruning_guidance():
    response = client.post(
        "/api/agri-chat",
        json={"question": "How do I prune mango trees?"},
    )

    assert response.json()["source"] == "mango-pruning"
    assert "prun" in response.json()["answer"].lower()


def test_agri_chat_yield_question_gets_crop_estimation_guidance():
    question = "How much yield can I expect from turmeric?"
    response = client.post("/api/agri-chat", json={"question": question})

    assert response.json()["source"] == "yield-estimate"
    assert "variety" in response.json()["answer"].lower()


def test_prediction_requires_trained_model(monkeypatch):
    monkeypatch.setattr(main, "_session", None)

    response = client.post(
        "/api/predict",
        files={"image": ("leaf.jpg", jpeg_image(), "image/jpeg")},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_NOT_READY"


def test_prediction_rejects_unsupported_media_type():
    response = client.post(
        "/api/predict",
        files={"image": ("leaf.gif", b"not an image", "image/gif")},
    )

    assert response.status_code == 415


def test_preprocessing_center_crops_wide_images_without_stretching():
    image = Image.new("RGB", (400, 200), "green")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 39, 199), fill="red")
    draw.rectangle((360, 0, 399, 199), fill="blue")

    processed = main.preprocess_image(image)

    assert processed.size == (224, 224)
    assert processed.getpixel((0, 112)) == (0, 128, 0)
    assert processed.getpixel((223, 112)) == (0, 128, 0)


def test_prediction_returns_crop_when_confident(monkeypatch):
    monkeypatch.setattr(main, "_session", FakeSession(np.array([[5.0] + [0.0] * 8], dtype=np.float32)))
    monkeypatch.setattr(main, "_input_name", "leaf_image")
    monkeypatch.setattr(main, "_labels", LABELS)
    monkeypatch.setattr(main, "_confidence_threshold", 0.5)

    response = client.post(
        "/api/predict",
        files={"image": ("leaf.jpg", jpeg_image(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "identified"
    assert response.json()["crop"] == "rice"
    assert response.json()["disease"] is None


def test_prediction_combines_confidence_across_conditions_for_crop(monkeypatch):
    labels = ["rice--healthy", "rice--brown-spot", "tomato--healthy"]
    monkeypatch.setattr(main, "_session", FakeSession(np.array([[2.0, 1.9, 2.2]], dtype=np.float32)))
    monkeypatch.setattr(main, "_input_name", "leaf_image")
    monkeypatch.setattr(main, "_labels", labels)
    monkeypatch.setattr(main, "_confidence_threshold", 0.6)

    response = client.post(
        "/api/predict",
        files={"image": ("leaf.jpg", jpeg_image(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "identified"
    assert response.json()["crop"] == "rice"
    assert response.json()["condition"] == "healthy"
    assert response.json()["confidence"] > 0.6


def test_prediction_returns_leaf_disease(monkeypatch):
    labels = ["rice--brown-spot"] + [f"{crop}--healthy" for crop in LABELS[1:]]
    monkeypatch.setattr(main, "_session", FakeSession(np.array([[5.0] + [0.0] * 8], dtype=np.float32)))
    monkeypatch.setattr(main, "_input_name", "leaf_image")
    monkeypatch.setattr(main, "_labels", labels)
    monkeypatch.setattr(main, "_confidence_threshold", 0.5)

    response = client.post(
        "/api/predict",
        files={"image": ("leaf.jpg", jpeg_image(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["crop"] == "rice"
    assert response.json()["condition"] == "brown-spot"
    assert response.json()["disease"] == "brown spot"


def test_prediction_abstains_below_threshold(monkeypatch):
    monkeypatch.setattr(main, "_session", FakeSession(np.zeros((1, 9), dtype=np.float32)))
    monkeypatch.setattr(main, "_input_name", "leaf_image")
    monkeypatch.setattr(main, "_labels", LABELS)
    monkeypatch.setattr(main, "_confidence_threshold", 0.5)

    response = client.post(
        "/api/predict",
        files={"image": ("leaf.jpg", jpeg_image(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_sure"
    assert response.json()["crop"] is None