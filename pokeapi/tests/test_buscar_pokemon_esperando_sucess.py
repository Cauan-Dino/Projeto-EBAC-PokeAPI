from fastapi.testclient import TestClient
from pytest_mock import MockerFixture 
import pytest
from pokeapi.main import app
from unittest.mock import MagicMock
from pokeapi.services.database.criacao_database import sessao_db
from sqlalchemy.orm import Session
import json

client = TestClient(app)



# Executa o redis antes de qualquer função teste
@pytest.fixture(autouse=True)
def inicializar_redis(mocker: MockerFixture):
    mock_redis = mocker.patch('pokeapi.routers.buscar_pokemon.redis_client', autospec=True)
    mock_redis.get.return_value = None

    return mock_redis


@pytest.fixture(autouse=True)
def mockar_sessao_db():
    """Sessão de banco de dados fake (SQLAlchemy Session mockada)."""
    mock_db = MagicMock(spec=Session)
    mock_db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[sessao_db] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.pop(sessao_db, None)


def requisicao_no_endpoint_da_pokeapi(code, json, mocker):
    """Mocka requsição no endpoint da PokeAPI"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = code
    mock_response.json.return_value = json
 
    mocker.patch('pokeapi.routers.buscar_pokemon.httpx2.AsyncClient.get', new_callable=mocker.AsyncMock, return_value=mock_response)
    return mock_response
 
# ====================================================================
# GET /pokemons/{pokemon_id} -> 200
# ====================================================================
class TestBuscarPokemonEspecifico200:

    def test_buscar_pokemon_especifico_sem_retorno_do_redis(self, mocker: MockerFixture):
        # Json que se vai ser retornado na requisição na PokeAPI
        json = {
            "id": 1,
            "height": 7,
            "weight": 69,
            "forms": [
                {"name": "bulbasaur"}
            ],
            "types": [
                {"type": {"name": "grass"}},
                {"type": {"name": "poison"}}
            ],
            "sprites": {
                "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
                "back_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/1.png"
            }
        }
    
        mock_pokeapi = requisicao_no_endpoint_da_pokeapi(code=200, json=json, mocker=mocker)
    
        # Mocka a função que envia os logs pro ElasticSearch
        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
        response = client.get('/pokemons/1')
        assert response.status_code == mock_pokeapi.status_code
        assert response.json()['id'] == mock_pokeapi.json()['id']


    def test_buscar_pokemon_especifico_com_retorno_do_redis(self, inicializar_redis, mocker: MockerFixture):
        mock_redis = inicializar_redis
    
        pokemon_cache_redis = {
            "id": 1,
            "name": "bulbasaur",
            "height": 7,
            "weight": 69,
            "types": ["grass", "poison"],
            "sprites": {
                "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
                "back_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/1.png"
            }
        }
    
        # Simula o get das informações do pokémon no cache
        mock_redis.get.return_value = json.dumps(pokemon_cache_redis)
    
        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
        # Dispara a requisição na API
        response = client.get('/pokemons/1')
    
        assert response.status_code == 200
        assert response.json()['name'] == pokemon_cache_redis['name']


# ====================================================================
# GET /pokemons -> 200
# ====================================================================
class TestBuscarTodosPokemons200:
    def test_buscar_todos_pokemons_com_retorno_do_redis(self, inicializar_redis, mocker: MockerFixture):
        # Limite e offset do query paramenters
        limit = 20
        offset = 0
    
        pokemon_cache_redis = {
            "data": [{"name": "bulbasaur", "url": "..."}],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "next": "url_proxima",
                "previous": None,
                "count": 1300
            }
        }
    
        # Simula o get no redis da URL da requisição feita
        mock_redis = inicializar_redis
        mock_redis.get.return_value = json.dumps(pokemon_cache_redis)
    
        # Mocka a função que registra log
        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
        # Dispara a requisição na API
        response = client.get(f'/pokemons?offset={offset}&limit={limit}')
    
        assert response.status_code == 200
        assert response.json()['data'][0]['name'] == pokemon_cache_redis['data'][0]['name']
        assert response.json()['pagination']['next'] == pokemon_cache_redis['pagination']['next']


    def test_buscar_todos_pokemons_sem_retorno_do_redis(self, mocker: MockerFixture):
        # Limite e offset do query paramenters
        limit = 1
        offset = 0
    
        # Mocka a função que registra log
        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
        # Json que se espera que retorne na Requisição na PokeAPI
        json = {
            "results": [
                {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon/1/"}
            ],
            "next": "https://pokeapi.co/api/v2/pokemon/?offset=1&limit=1",
            "previous": None,
            "count": 1351
        }
    
        # Faz uma requisição na PokeAPI
        mock_requisicao = requisicao_no_endpoint_da_pokeapi(code=200, json=json, mocker=mocker)

        mocker.patch('pokeapi.services.pokemon_service.requisicao_pokeapi.redis_client.set')
    
        response = client.get(f'/pokemons?offset={offset}&limit={limit}')
    
        assert response.status_code == mock_requisicao.status_code
        assert response.json()['pagination']['next'] == mock_requisicao.json()['next']