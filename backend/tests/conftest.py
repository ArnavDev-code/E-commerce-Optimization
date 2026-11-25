"""Pytest fixtures for FunnelLeak AI test suite."""

import os
import pytest
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Setup test environment variables
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEMO_MODE"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-funnelleak-ai"

from app.database import Base
import app.models  # Register all models on Base.metadata

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    bind=engine_test, autocommit=False, autoflush=False, expire_on_commit=False
)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provide a fresh isolated database session for each test function."""
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)
