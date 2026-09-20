import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+psycopg2://event_admin:event_secure_pass_2026@localhost:5433/event_booking_test_db"

engine_test = create_engine(
    TEST_DATABASE_URL,
    pool_size=30,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client():
    # Clean tables before each test for test isolation
    with engine_test.connect() as conn:
        conn.execute(text("TRUNCATE TABLE bookings, events, users RESTART IDENTITY CASCADE;"))
        conn.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
