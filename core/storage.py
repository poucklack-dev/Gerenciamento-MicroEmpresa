# core/storage.py
import os
import logging
import time
from io import BytesIO
from uuid import uuid4
from werkzeug.utils import secure_filename
from google.cloud import storage as gcs

logger = logging.getLogger(__name__)

class LocalStorage:
    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)

    def _get_path(self, key):
        return os.path.join(self.upload_folder, key)

    def save(self, file, subdir):
        self._validate_subdir(subdir)
        filename = self._secure_filename(file.filename)
        key = f"{subdir}/{filename}"
        
        subdir_path = os.path.join(self.upload_folder, subdir)
        if not os.path.exists(subdir_path):
            os.makedirs(subdir_path)
            
        full_path = self._get_path(key)
        file.save(full_path)
        return key

    def save_bytes(self, data, subdir, filename):
        """Persist raw bytes using a stable key (used by facial data)."""
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
            # Handle case where file doesn't exist
            pass

    def open(self, key):
        with open(self._get_path(key), 'rb') as f:
            return f.read()

    def get_url(self, key):
        return f"/media/{key}"

    def _secure_filename(self, filename):
        filename = secure_filename(filename)
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValueError("Invalid filename")
        # Add a unique prefix to avoid filename collisions
        return f"{uuid4().hex}_{filename}"

    def _validate_subdir(self, subdir):
        allowed_subdirs = [
            'contas_pagar', 'contratos', 'custos', 'documentos', 
            'equipe_campo', 'faces', 'fornecedores', 'recebimentos', 'data'
        ]
        if subdir not in allowed_subdirs:
            raise ValueError(f"Invalid subdir: {subdir}")

class GCSStorage:
    def __init__(self, bucket_name, upload_prefix='uploads'):
        self.client = gcs.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.upload_prefix = upload_prefix

    def save(self, file, subdir):
        start_time = time.perf_counter()
        self._validate_subdir(subdir)
        filename = self._secure_filename(file.filename)
        key = f"{self.upload_prefix}/{subdir}/{filename}"
        
        logger.info(f"Iniciando upload GCS: {key}")
        
        try:
            blob = self.bucket.blob(key)
            content_type = getattr(file, 'mimetype', 'application/octet-stream')
            blob.upload_from_file(file.stream, rewind=True, content_type=content_type, timeout=60)
            
            elapsed = time.perf_counter() - start_time
            logger.info(f"Upload GCS concluído: {key} em {elapsed:.2f}s")
            return key
        except Exception as e:
            logger.exception(f"Erro no upload GCS para {key}: {str(e)}")
            raise

    def save_bytes(self, data, subdir, filename):
        self._validate_subdir(subdir)
        safe_name = secure_filename(filename)
        if not safe_name:
            raise ValueError("Invalid filename")
        key = f"{subdir}/{safe_name}"
        self.bucket.blob(self._blob_key(key)).upload_from_file(BytesIO(data), rewind=True, timeout=60)
        return key

    def key_exists(self, key):
        return self.bucket.blob(self._blob_key(key)).exists()

    def delete(self, key):
        blob = self.bucket.blob(key)
        blob.delete()

    def open(self, key):
        blob = self.bucket.blob(self._blob_key(key))
        return blob.download_as_bytes()

    def get_url(self, key):
        return f"/media/{key}"

    def _blob_key(self, key):
        prefix = f"{self.upload_prefix}/"
        return key if key.startswith(prefix) else f"{prefix}{key}"

    def _secure_filename(self, filename):
        filename = secure_filename(filename)
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValueError("Invalid filename")
        return f"{uuid4().hex}_{filename}"

    def _validate_subdir(self, subdir):
        allowed_subdirs = [
            'contas_pagar', 'contratos', 'custos', 'documentos', 
            'equipe_campo', 'faces', 'fornecedores', 'recebimentos', 'data'
        ]
        if subdir not in allowed_subdirs:
            raise ValueError(f"Invalid subdir: {subdir}")


_storage_instance = None

def get_storage():
    global _storage_instance
    if _storage_instance is None:
        driver = os.getenv('STORAGE_DRIVER', 'local').strip().lower()
        if driver == 'gcs':
            bucket_name = os.getenv('GCS_BUCKET')
            if not bucket_name:
                raise ValueError("GCS_BUCKET environment variable must be set for GCS storage")
            upload_prefix = os.getenv('UPLOADS_PREFIX', 'uploads')
            _storage_instance = GCSStorage(bucket_name=bucket_name, upload_prefix=upload_prefix)
        else:
            local_path = os.getenv("LOCAL_STORAGE_PATH")
            if not local_path:
                env_name = (os.getenv("ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
                local_path = "/tmp/uploads" if env_name in {"prod", "production"} else "./uploads"
            _storage_instance = LocalStorage(upload_folder=local_path)
    return _storage_instance
