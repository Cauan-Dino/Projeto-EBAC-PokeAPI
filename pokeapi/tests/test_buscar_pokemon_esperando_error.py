from fastapi.testclient import TestClient
from pokeapi.main import app
from pytest_mock import MockerFixture
from pokeapi.services.database.criacao_database import sessao_db
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
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


# ====================================================================
# GET /pokemons/{pokemon_id} -> 404
# ====================================================================
class TestBuscarPokemonEspecifico404:
    def test_buscar_pokemon_especifico_esperando_erro_404(self, mocker: MockerFixture):
        mock_requisicao_pokeapi = requisicao_no_endpoint_da_pokeapi(code=404, mocker=mocker)

        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

        response = client.get('/pokemons/99999')
        assert response.status_code == mock_requisicao_pokeapi.status_code


# ====================================================================
# GET /pokemons -> 400
# ====================================================================
class TestBuscarTodosPokemons400:
    def test_buscar_todos_pokemons_esperando_erro_400(self, mocker: MockerFixture):
        mock_requisicao_pokeapi = requisicao_no_endpoint_da_pokeapi(code=400, mocker=mocker)

        mocker.patch('pokeapi.routers.buscar_pokemon.verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache', new_callable=mocker.AsyncMock)

        response = client.get('/pokemons?limit=0&offset=-1')
        assert response.status_code == mock_requisicao_pokeapi.status_code


# ====================================================================
# GET /pokemons/{pokemon_id} -> 400 (pokémon excluído logicamente)
# ====================================================================
class TestBuscarPokemonEspecificoExcluido:
    def test_buscar_pokemon_excluido_retorna_400(self, mocker: MockerFixture):
        pokemon_excluido = MagicMock(pokemon_excluido=True)
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = pokemon_excluido
        app.dependency_overrides[sessao_db] = lambda: mock_db

        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

        try:
            response = client.get('/pokemons/25')
        finally:
            app.dependency_overrides.pop(sessao_db, None)

        assert response.status_code == 400
        assert response.json()['detail'] == 'Pokémon está excluido!'


# ====================================================================
# GET /pokemons/{pokemon_id} -> 500 (erro interno inesperado)
# ====================================================================
class TestBuscarPokemonEspecificoErroInterno:
    def test_erro_inesperado_no_banco_retorna_500(self, mocker: MockerFixture):
        mock_db = MagicMock(spec=Session)
        mock_db.query.side_effect = Exception("falha inesperada de conexão")
        app.dependency_overrides[sessao_db] = lambda: mock_db

        mocker.patch('pokeapi.routers.buscar_pokemon.registrar_log_de_buscar_pokemon', new_callable=mocker.AsyncMock)

        try:
            response = client.get('/pokemons/25')
        finally:
            app.dependency_overrides.pop(sessao_db, None)

        assert response.status_code == 500
