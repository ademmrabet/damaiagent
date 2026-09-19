"""
Test-session setup for the authentication layer.

Two problems this solves:

1. webapp/auth.py reads JWT_SECRET_KEY from the environment at import
   time and refuses to start without one (on purpose - see that
   file's comment on why there's no default). Any test module that
   imports webapp.backend (which imports webapp.auth) would otherwise
   crash at collection, not just at test-run time. Setting it here,
   at conftest module level, guarantees it exists before pytest
   imports any test file in this directory.

2. Several auth tests (and test_backend.py's dashboard test) depend
   on "the first account ever created becomes administrator" - which
   only means something if the users table is actually empty when
   the test runs. Since every test file in this suite shares one
   database (DATABASE_URL is read once, at import time, by
   webapp/db.py), a signup in one test file would otherwise leak into
   the next, making pass/fail depend on test execution order. The
   autouse fixture below wipes the table before and after every test
   function, so each test's "first user" is really first.
"""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests_auth.db")

import pytest

from webapp.db import Base, engine
from webapp.models import User  # noqa: F401 - import registers the table on Base


@pytest.fixture(autouse=True)
def _clean_users_table():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(User.__table__.delete())
    yield
    with engine.begin() as conn:
        conn.execute(User.__table__.delete())
