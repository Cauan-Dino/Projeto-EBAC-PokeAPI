import os
os.environ.setdefault('URL_DB', 'sqlite:///:memory:')
os.environ.setdefault('ES_HOST', 'elasticsearch')
os.environ.setdefault('ES_PORT', '9200')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from pokeapi.services.database.criacao_database import Base
from pokeapi.services.database.models import CadastroPokemon
from pokeapi.services.pokemon_service.formatador import (
    formatar_pokemon_da_pokeapi,
    pokemon_orm_para_dict,
)


@pytest.fixture
def db_session():
    """Banco SQLite em memória, isolado por teste."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestCadastroPokemonModelo:

    def test_cria_pokemon_com_excluido_false_por_padrao(self, db_session):
        pokemon = CadastroPokemon(
            pokemon_id=1,
            pokemon_name="bulbasaur",
            pokemon_height=7,
            pokemon_weight=69,
            pokemon_type=["grass", "poison"],
            pokemon_sprites={"front_default": "a", "back_default": "b"},
        )
        db_session.add(pokemon)
        db_session.commit()
        db_session.refresh(pokemon)

        assert pokemon.pokemon_excluido is False

    def test_nome_duplicado_viola_constraint_unique(self, db_session):
        db_session.add(CadastroPokemon(
            pokemon_id=1, pokemon_name="pikachu", pokemon_height=4,
            pokemon_weight=60, pokemon_type=["electric"],
            pokemon_sprites={"front_default": None, "back_default": None},
        ))
        db_session.commit()

        db_session.add(CadastroPokemon(
            pokemon_id=2, pokemon_name="pikachu", pokemon_height=4,
            pokemon_weight=60, pokemon_type=["electric"],
            pokemon_sprites={"front_default": None, "back_default": None},
        ))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_soft_delete_nao_remove_a_linha(self, db_session):
        pokemon = CadastroPokemon(
            pokemon_id=1, pokemon_name="pikachu", pokemon_height=4,
            pokemon_weight=60, pokemon_type=["electric"],
            pokemon_sprites={"front_default": None, "back_default": None},
        )
        db_session.add(pokemon)
        db_session.commit()

        pokemon.pokemon_excluido = True
        db_session.commit()

        # A linha continua existindo no banco, só a flag muda
        resultado = db_session.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == 1).first()
        assert resultado is not None
        assert resultado.pokemon_excluido is True


class TestFormatadorSchemaCanonico:

    def test_formatar_pokemon_da_pokeapi_gera_schema_canonico(self):
        json_pokeapi = {
            "id": 25,
            "forms": [{"name": "pikachu"}],
            "height": 4,
            "weight": 60,
            "types": [{"type": {"name": "electric"}}],
            "sprites": {"front_default": "front.png", "back_default": "back.png"},
        }

        resultado = formatar_pokemon_da_pokeapi(json_pokeapi)

        assert resultado == {
            "pokemon_id": 25,
            "pokemon_name": "pikachu",
            "pokemon_height": 4,
            "pokemon_weight": 60,
            "pokemon_type": ["electric"],
            "pokemon_sprites": {"front_default": "front.png", "back_default": "back.png"},
        }

    def test_pokemon_orm_para_dict_usa_as_mesmas_chaves(self, db_session):
        pokemon = CadastroPokemon(
            pokemon_id=25, pokemon_name="pikachu", pokemon_height=4,
            pokemon_weight=60, pokemon_type=["electric"],
            pokemon_sprites={"front_default": "front.png", "back_default": "back.png"},
        )
        db_session.add(pokemon)
        db_session.commit()

        resultado = pokemon_orm_para_dict(pokemon)
        chaves_esperadas = set(formatar_pokemon_da_pokeapi({
            "id": 1, "forms": [{"name": "x"}], "height": 1, "weight": 1,
            "types": [], "sprites": {"front_default": None, "back_default": None},
        }).keys())

        # As duas fontes de dados (banco e PokeAPI) devem produzir o mesmo schema
        assert set(resultado.keys()) == chaves_esperadas
