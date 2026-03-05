import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from card_retrieval.storage.orm_models import Base
from card_retrieval.storage.repository import PromotionRepository


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def repo(db_session):
    """Create a repository with in-memory database."""
    return PromotionRepository(session=db_session)
