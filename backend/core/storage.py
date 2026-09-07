import os
from uuid import uuid4

from werkzeug.utils import secure_filename


BLOCKED_EXTENSIONS = {
    "bat", "cmd", "com", "exe", "html", "htm", "js", "msi", "php",
    "ps1", "py", "sh", "svg",
}
ALLOWED_SUBDIRS = {
    "contas_pagar", "contratos", "custos", "documentos", "equipe_campo",
    "faces", "fornecedores", "recebimentos", "data",
}


def validate_image_upload(file, allowed_formats=("JPEG", "PNG")) -> bool:
    """Validate an uploaded image by decoding its content."""
    if not file or not getattr(file, "filename", ""):
        return False
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return False
    try:
        image = Image.open(file.stream)
        image.verify()
        return image.format in allowed_formats
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        file.stream.seek(0)


class LocalStorage:
    def __init__(self, upload_folder="uploads"):
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)

    def _get_path(self, key):
        root = os.path.abspath(self.upload_folder)
        path = os.path.abspath(os.path.join(root, key))
        if os.path.commonpath([root, path]) != root:
            raise ValueError("Invalid storage key")
        return path

    def save(self, file, subdir):
        self._validate_subdir(subdir)
        filename = self._secure_filename(file.filename)
        key = f"{subdir}/{filename}"
        full_path = self._get_path(key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        file.save(full_path)
        return key

    def save_bytes(self, data, subdir, filename):
        self._validate_subdir(subdir)
        safe_name = secure_filename(filename)
        if not safe_name:
            raise ValueError("Invalid filename")
        key = f"{subdir}/{safe_name}"
        full_path = self._get_path(key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as destination:
            destination.write(data)
        return key

    def key_exists(self, key):
        return os.path.isfile(self._get_path(key))

    def delete(self, key):
        try:
            os.remove(self._get_path(key))
        except FileNotFoundError:
            pass

    def open(self, key):
        with open(self._get_path(key), "rb") as source:
            return source.read()

    def get_url(self, key):
        return f"/media/{key}"

    @staticmethod
    def _secure_filename(filename):
        filename = secure_filename(filename)
        if not filename:
            raise ValueError("Invalid filename")
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension in BLOCKED_EXTENSIONS:
            raise ValueError("File type not allowed")
        return f"{uuid4().hex}_{filename}"

    @staticmethod
    def _validate_subdir(subdir):
        if subdir not in ALLOWED_SUBDIRS:
            raise ValueError(f"Invalid subdir: {subdir}")


_storage_instance = None


def get_storage():
    global _storage_instance
    if _storage_instance is None:
        local_path = os.getenv("LOCAL_STORAGE_PATH", "./uploads")
        _storage_instance = LocalStorage(upload_folder=local_path)
    return _storage_instance
