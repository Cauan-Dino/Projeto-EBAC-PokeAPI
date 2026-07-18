from fastapi.testclient import TestClient
from pokeapi.main import app
from pytest_mock import MockerFixture
import httpx2
import pytest

client = TestClient(app)

# Executa a função verificar_mudanca_pokemons_pokeapi
def requisicao_no_endpoint_da_pokeapi(code: int, mocker: MockerFixture):
    # Simula uma requisição na PokeAPI
    mock_requisicao_pokeapi = mocker.MagicMock(spec=httpx2.Response)
    mock_requisicao_pokeapi.status_code = code

    # Mocka o get na PokeAPI
    mock_client = mocker.AsyncMock(spec=httpx2.AsyncClient)
    mock_client.get.return_value = mock_requisicao_pokeapi

    # Mocka a classe httpx2.AsyncClient
    mock_async_client = mocker.patch('httpx2.AsyncClient', autospec=True)
    mock_async_client.return_value.__aenter__.return_value = mock_client

    return mock_requisicao_pokeapi




# /pokemons esperando 502
def test_buscar_todos_os_pokemons_esperando_erro_diferente_de_200(mocker: MockerFixture):
    limit = 1
    offset = 0

    mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

    mock_requisicao_pokeapi = requisicao_no_endpoint_da_pokeapi(code=502, mocker=mocker)

    # Lança uma requisição no endpoint pokemons
    response = client.get(f'/pokemons?offset={offset}&limit={limit}')
    assert response.status_code == mock_requisicao_pokeapi.status_code



# /pokemons/{pokemon_id} esperando erro 404
def test_buscar_pokemon_especifico_esperando_erro_404(mocker: MockerFixture):
    mock_requisicao_pokeapi = requisicao_no_endpoint_da_pokeapi(code=404, mocker=mocker)

    mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

    response = client.get('/pokemons/99999')
    assert response.status_code == mock_requisicao_pokeapi.status_code



# /pokemons/{pokemon_id} esperando erro 502
def test_buscar_pokemon_especifico_esperando_erro_502(mocker: MockerFixture):
    mock_requisicao_pokeapi = requisicao_no_endpoint_da_pokeapi(code=502, mocker=mocker)

    mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)
    
    response = client.get('/pokemons/1')
    assert response.status_code == mock_requisicao_pokeapi.status_code