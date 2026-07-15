"""
Shared test fixtures for unit-level write-safety tests.

The rest of this repo's test suite (test_wp_placement.py, test_worker_queue.py,
etc.) is entirely black-box HTTP testing against a live running server
(requests.post(BASE_URL + ...)) and does not import any backend modules
directly, so this conftest does not affect it.

test_wp_write_safety_unit.py is different: it exercises services/wp_write_safety.py,
services/wp_client.py, and services/worker_queue.py directly, without a live
server or a real MongoDB, using an in-memory async Mongo double
(mongomock-motor). services/field_listing.py (imported transitively by
services/worker_queue.py) depends on the `emergentintegrations` package,
which is an internal Emergent-platform dependency not published to PyPI and
not installable in this sandbox -- it is stubbed out here purely so the
import succeeds; nothing in these tests exercises that stub.
"""
import os
import sys
import types

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ts_ops_write_safety_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")

# ---- Stub the unavailable emergentintegrations dependency ----
if "emergentintegrations" not in sys.modules:
    emergent_pkg = types.ModuleType("emergentintegrations")
    llm_pkg = types.ModuleType("emergentintegrations.llm")
    chat_mod = types.ModuleType("emergentintegrations.llm.chat")

    class _Stub:
        def __init__(self, *a, **kw):
            pass

    chat_mod.LlmChat = _Stub
    chat_mod.UserMessage = _Stub
    chat_mod.ImageContent = _Stub

    sys.modules["emergentintegrations"] = emergent_pkg
    sys.modules["emergentintegrations.llm"] = llm_pkg
    sys.modules["emergentintegrations.llm.chat"] = chat_mod

import pytest
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture
def mock_db(monkeypatch):
    """
    Fresh in-memory Mongo database per test, patched into every module that
    imported `db` by name (each module bound its own reference at import
    time via `from database import db`, so the patch must target each
    module's namespace individually -- `from database import db` copies a
    reference, it isn't a live link back to database.db).
    """
    client = AsyncMongoMockClient()
    fake_db = client["ts_ops_write_safety_test"]

    import database
    monkeypatch.setattr(database, "db", fake_db)

    import services.wp_write_safety as wws
    monkeypatch.setattr(wws, "db", fake_db)

    import services.wp_client as wpc
    monkeypatch.setattr(wpc, "db", fake_db)

    import services.worker_queue as wq
    monkeypatch.setattr(wq, "db", fake_db)

    import services.helpers as helpers
    monkeypatch.setattr(helpers, "db", fake_db)

    import auth
    monkeypatch.setattr(auth, "db", fake_db)

    # Route modules are only imported the FIRST time any test builds the
    # `client` fixture; on later tests `import routes.x` is a no-op (Python
    # caches modules), so each route module's own `db` reference must also
    # be repatched every test, not just the service layer.
    import routes.wp_placement as wp_placement_route
    monkeypatch.setattr(wp_placement_route, "db", fake_db)

    import routes.worker_queue as worker_queue_route
    monkeypatch.setattr(worker_queue_route, "db", fake_db)

    import services.execution_manifest as execution_manifest_svc
    monkeypatch.setattr(execution_manifest_svc, "db", fake_db)

    return fake_db
