from fastapi.testclient import TestClient
from pytest_mock import MockerFixture 
import pytest
from pokeapi.main import app
from fastapi import BackgroundTasks
import json
import httpx2

client = TestClient(app)



# Executa o redis antes de qualquer função teste
@pytest.fixture(autouse=True)
def inicializar_redis(mocker: MockerFixture):
    mock_redis = mocker.patch('pokeapi.routers.buscar_pokemon.redis_client', autospec=True)
    mock_redis.get.return_value = None

    return mock_redis


# Executa a função verificar_mudanca_pokemons_pokeapi
def requisicao_no_endpoint_da_pokeapi(code: int, json: dict | None, mocker: MockerFixture):
    # Simula uma requisição na PokeAPI
    mock_requisicao_pokeapi = mocker.MagicMock(spec=httpx2.Response)
    mock_requisicao_pokeapi.status_code = code
    if json is not None:
        mock_requisicao_pokeapi.json.return_value = json

    # Mocka o get na PokeAPI
    mock_client = mocker.AsyncMock(spec=httpx2.AsyncClient)
    mock_client.get.return_value = mock_requisicao_pokeapi

    # Mocka a classe httpx2.AsyncClient
    mock_async_client = mocker.patch('httpx2.AsyncClient', autospec=True)
    mock_async_client.return_value.__aenter__.return_value = mock_client

    return mock_requisicao_pokeapi






def test_buscar_pokemon_especifico_sem_retorno_do_redis(mocker: MockerFixture):
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




def test_buscar_pokemon_especifico_com_retorno_do_redis(inicializar_redis, mocker: MockerFixture):
    mock_redis = inicializar_redis

    # Dicionário pego no get do Redis
    pokemon_cache_redis = {
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

    # Simula o get das informações do pokémon no cache
    mock_redis.get.return_value = json.dumps(pokemon_cache_redis)
    
    mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
    # Dispara a requisição na API
    response = client.get('/pokemons/1')
    
    assert response.status_code == 200
    assert response.json()['forms'][0]['name'] == pokemon_cache_redis['forms'][0]['name'] 




def test_buscar_todos_pokemons_com_retorno_do_redis(inicializar_redis,mocker: MockerFixture):
    # Limite e offset do query paramenters
    limit = 20
    offset = 0
    
    # Dicionário pego no get do Redis
    pokemon_cache_redis = {
        "results": [{"name": "bulbasaur", "url": "..."}],
        "next": "url_proxima",
        "previous": None,
        "count": 1300
        }

    # Simula o get no redis da URL da requisição feita
    mock_redis = inicializar_redis
    mock_redis.get.return_value = json.dumps(pokemon_cache_redis)
    
    # Mocka o método add_task da Classe BackgroundTasks
    mock_background = mocker.MagicMock(spec=BackgroundTasks)
    mock_background.add_task.return_value = None

    # Mocka a função que registra log
    mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

    # Dispara a requisição na API   
    response = client.get(f'/pokemons?offset={offset}&limit={limit}')
    
    assert response.status_code == 200
    assert response.json()['results'][0]['name'] == pokemon_cache_redis['results'][0]['name']
     



def test_buscar_todos_pokemons_sem_retorno_do_redis(mocker: MockerFixture):    
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

    mocker.patch('pokeapi.routers.buscar_pokemon.redis_client.set') # Mocka o set do redis

    response = client.get(f'/pokemons?offset={offset}&limit={limit}')
    
    assert response.status_code == mock_requisicao.status_code
    assert response.json()['pagination']['next']== mock_requisicao.json()['next']