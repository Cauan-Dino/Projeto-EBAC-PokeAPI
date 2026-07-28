import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("URL_DB", "sqlite:///./test.db")

from pokeapi.main import app
from pokeapi.services.database.criacao_database import Base, sessao_db


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(session):
    app.dependency_overrides[sessao_db] = lambda: session
    with patch("pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon", new=AsyncMock()), \
         patch("pokeapi.routers.alterar_deletar_criar_pokemons.registrar_log_de_buscar_pokemon", new=AsyncMock()):
        yield TestClient(app)
    app.dependency_overrides.clear()
