from flask import Blueprint, abort, jsonify, session
import os
import logging
import traceback
import time
from core.storage import get_storage, GCSStorage
from flask_login import current_user

diag_bp = Blueprint('diag', __name__, url_prefix='/api/diag')
logger = logging.getLogger(__name__)

def _debug_routes_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_ROUTES", "").strip().lower() in {"1", "true", "yes", "on"}

def _is_admin() -> bool:
    user_session = session.get("usuarios") or {}
    cargo = str(user_session.get("cargo", "")).lower()
    if user_session.get("id") and "admin" in cargo:
        return True
    return bool(getattr(current_user, "is_authenticated", False) and getattr(current_user, "is_admin", False))

@diag_bp.route('/gcs', methods=['GET'])
def diag_gcs():
    if not _debug_routes_enabled():
        abort(404)
    if not _is_admin():
        abort(403)

    start_time = time.perf_counter()
    result = {
        "driver": os.getenv('STORAGE_DRIVER', 'local'),
        "bucket": os.getenv('GCS_BUCKET'),
        "prefix": os.getenv('UPLOADS_PREFIX', 'uploads'),
        "steps": []
    }
    
    try:
        storage = get_storage()
        result['steps'].append("get_storage() ok")
        
        if isinstance(storage, GCSStorage):
            # Check if bucket exists
            if storage.bucket.exists():
                result['steps'].append("bucket.exists() ok")
            else:
                result['steps'].append("bucket.exists() failed")
                return jsonify({"ok": False, "error": "Bucket not found", "details": result}), 500
            
            # Test write/delete (ping)
            test_key = f"{storage.upload_prefix}/_diag/ping_{int(time.time())}.txt"
            blob = storage.bucket.blob(test_key)
            blob.upload_from_string("pong", content_type="text/plain", timeout=10)
            result['steps'].append("write ok")
            
            blob.delete(timeout=10)
            result['steps'].append("delete ok")
        else:
            result['steps'].append("Local storage check skipped")

        result['ok'] = True
        result['duration'] = time.perf_counter() - start_time
        return jsonify(result)

    except Exception as e:
        logger.exception("GCS Diag failed")
        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
            "details": result
        }), 500
