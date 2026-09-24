"""API composition layer.

``app/backend/README.md`` listed ``api/`` as "future expansion" while the
router assembly lived in ``routes/__init__.py`` mixed in with the endpoint
modules. This package now owns composition — which routers exist, and which
cross-cutting dependencies guard them — leaving ``routes/`` to hold only the
endpoint implementations.
"""

from app.backend.api.v1 import api_router

__all__ = ["api_router"]
