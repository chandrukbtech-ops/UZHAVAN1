from io import BytesIO
import json
from urllib.error import HTTPError

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image, ImageDraw

from backend.app import main


client = TestClient(main.app)
LABELS = [
    "rice--healthy", "wheat--healthy", "corn--healthy", "sugarcane--healthy", "cotton--healthy",
    "soybean--healthy", "mustard--healthy", "tomato--healthy", "brinjal--healthy",
]


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


def test_agri_chat_uses_configured_llm_and_reports_generated_mode(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "Check the rice root-zone moisture before irrigating."}}],
            }).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setenv("AGRI_LLM_API_KEY", "test-key")
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
    assert body["assistant_mode"] == "generated"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["timeout"] == 18
    assert captured["payload"]["model"] == "gemini-2.5-flash"
    assert captured["payload"]["messages"][-2]["content"] == "I planted last week."
    assert "Retrieved farming notes:" in captured["payload"]["messages"][-1]["content"]


def test_agri_chat_falls_back_to_local_notes_when_llm_fails(monkeypatch):
    monkeypatch.setenv("AGRI_LLM_API_KEY", "test-key")

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


def test_agri_chat_logs_provider_http_error_without_exposing_key(monkeypatch, caplog):
    api_key = "test-key"
    monkeypatch.setenv("AGRI_LLM_API_KEY", api_key)

    def reject_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=BytesIO(json.dumps({
                "error": {"message": f"Key {api_key} is not allowed for this project."},
            }).encode()),
        )

    monkeypatch.setattr(main, "urlopen", reject_urlopen)

    response = client.post(
        "/api/agri-chat",
        json={"question": "How often should I irrigate rice?"},
    )

    assert response.status_code == 200
    assert response.json()["assistant_mode"] == "local_notes"
    assert "HTTP 403" in caplog.text
    assert "[redacted] is not allowed" in caplog.text
    assert api_key not in caplog.text


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