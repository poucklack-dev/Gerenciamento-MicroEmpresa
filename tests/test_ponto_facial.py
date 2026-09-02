import pickle

import cv2
import numpy as np

from backend.ponto import SmartFacialSystem


class MemoryStorage:
    def __init__(self, initial=None):
        self.files = dict(initial or {})

    def key_exists(self, key):
        return key in self.files

    def open(self, key):
        return self.files[key]

    def save_bytes(self, data, subdir, filename):
        key = f"{subdir}/{filename}"
        self.files[key] = data
        return key


def facial_system(storage=None):
    system = SmartFacialSystem.__new__(SmartFacialSystem)
    system.storage = storage or MemoryStorage()
    system.encodings = {}
    system._lock = __import__("threading").RLock()
    system._hog = cv2.HOGDescriptor((128, 128), (16, 16), (8, 8), (8, 8), 9)
    return system


def test_encoding_is_normalized_and_recognizes_same_face(monkeypatch):
    system = facial_system()
    face = np.zeros((128, 128), dtype=np.uint8)
    cv2.circle(face, (64, 64), 42, 180, -1)
    cv2.circle(face, (49, 55), 7, 20, -1)
    cv2.circle(face, (79, 55), 7, 20, -1)
    cv2.ellipse(face, (64, 78), (18, 9), 0, 0, 180, 30, 3)
    descriptor = system.gerar_encoding(face)
    system.encodings["123.456.789-01"] = [descriptor]
    monkeypatch.setattr(system, "processar_imagem", lambda _: (face, None))

    success, result = system.reconhecer_face(b"image")

    assert np.isclose(np.linalg.norm(descriptor), 1.0)
    assert success is True
    assert result["cpf"] == "123.456.789-01"
    assert result["confidence"] == 1.0


def test_new_profile_is_versioned_and_persisted(monkeypatch):
    storage = MemoryStorage()
    system = facial_system(storage)
    face = np.tile(np.arange(128, dtype=np.uint8), (128, 1))
    monkeypatch.setattr(system, "processar_imagem", lambda _: (face, None))

    success, _ = system.cadastrar_rosto("12345678901", b"image")
    payload = pickle.loads(storage.files["data/facial_encodings.pkl"])

    assert success is True
    assert payload["version"] == SmartFacialSystem.FORMAT_VERSION
    assert "123.456.789-01" in payload["profiles"]
    assert system.cpf_tem_rosto("12345678901") is True


def test_legacy_brightness_histograms_are_not_loaded():
    legacy = {"123.456.789-01": np.ones(256, dtype=np.float32)}
    storage = MemoryStorage({"data/facial_encodings.pkl": pickle.dumps(legacy)})
    system = facial_system(storage)

    system.load_encodings()

    assert system.encodings == {}
    assert system.cpf_tem_rosto("12345678901") is False
