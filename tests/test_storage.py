from io import BytesIO

from core.storage import LocalStorage
from werkzeug.datastructures import FileStorage


def test_local_storage_supports_stable_binary_keys(tmp_path):
    storage = LocalStorage(str(tmp_path))

    key = storage.save_bytes(b"facial-data", "data", "facial_encodings.pkl")

    assert key == "data/facial_encodings.pkl"
    assert storage.key_exists(key)
    assert storage.open(key) == b"facial-data"


def test_local_storage_regular_upload_keeps_unique_name(tmp_path):
    storage = LocalStorage(str(tmp_path))
    upload = FileStorage(stream=BytesIO(b"document"), filename="arquivo.pdf")

    key = storage.save(upload, "documentos")

    assert key.startswith("documentos/")
    assert key.endswith("_arquivo.pdf")
    assert storage.open(key) == b"document"
