from __future__ import annotations

import mimetypes
import os
from io import BytesIO

from flask import Blueprint, abort, redirect, request, send_file, session, url_for
from flask_login import current_user

from core.storage import GCSStorage, LocalStorage, get_storage


media_bp = Blueprint("media", __name__)


def _is_authenticated() -> bool:
    if "usuarios" in session:
        return True
    try:
        return bool(getattr(current_user, "is_authenticated", False))
    except Exception:
        return False


def _should_download(content_type: str) -> bool:
    if not content_type:
        return True
    if content_type.startswith("image/"):
        return False
    if content_type in {"application/pdf"}:
        return False
    return True


@media_bp.get("/media/<path:key>")
def get_media(key: str):
    if not _is_authenticated():
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            return redirect(url_for("login.login"))
        abort(401)

    if not key or ".." in key or key.startswith(("/", "\\")) or "\x00" in key:
        abort(400)

    storage = get_storage()

    if isinstance(storage, LocalStorage):
        root = os.path.abspath(storage.upload_folder)
        path = os.path.abspath(os.path.join(root, key))
        if os.path.commonpath([path, root]) != root:
            abort(400)
        if not os.path.exists(path):
            abort(404)

        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return send_file(
            path,
            mimetype=content_type,
            as_attachment=_should_download(content_type),
            download_name=os.path.basename(path),
        )

    if isinstance(storage, GCSStorage):
        blob = storage.bucket.blob(key)
        if not blob.exists():
            abort(404)

        data = blob.download_as_bytes(timeout=60)
        content_type = blob.content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        return send_file(
            BytesIO(data),
            mimetype=content_type,
            as_attachment=_should_download(content_type),
            download_name=os.path.basename(key),
        )

    abort(500)

