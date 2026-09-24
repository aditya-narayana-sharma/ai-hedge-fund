"""AI Hedge Fund backend.

There used to be a sys.path shim here that appended ``<root>/src`` as a
"temporary solution". It was inert — every import in this package uses the
``src.*`` prefix, which resolves from the repository root — and it encouraged
running uvicorn from ``app/backend``, where ``app.backend.routes`` cannot be
imported at all. Start the server from the repository root instead:

    poetry run uvicorn app.backend.main:app --reload
"""
