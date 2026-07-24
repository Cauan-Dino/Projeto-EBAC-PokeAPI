

from unittest.mock import MagicMock, AsyncMock, patch
import os
os.environ['URL_DB'] = "sqlite:///./test.db" 
os.environ['ES_HOST'] = 'elasticsearch'
os.environ['ES_PORT'] = '9200'
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
 
# ------------------------------------------------------------------
# AJUSTE AQUI o caminho real do módulo do router
# ------------------------------------------------------------------
MODULE_PATH = "pokeapi.routers.alterar_deletar_criar_pokemons"
 
from importlib import import_module
 
router_module = import_module(MODULE_PATH)
router = router_module.router
sessao_db = router_module.sessao_db
 

@pytest.fixture
def mock_db():
    """Sessão de banco de dados fake (SQLAlchemy Session mockada)."""
    return MagicMock()
 
 
@pytest.fixture
def client(mock_db):
    """Cliente de teste com a dependência do banco sobrescrita."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[sessao_db] = lambda: mock_db
    return TestClient(app)
 
 
@pytest.fixture(autouse=True)
def mock_log():
    """Evita que os testes mandem log de verdade pro Elasticsearch."""
    with patch(
        f"{MODULE_PATH}.registrar_log_de_buscar_pokemon",
        new=AsyncMock(return_value=None),
    ) as m:
        yield m
 
 
def fake_pokeapi_response(status_code=200, json_data=None):
    """Monta uma resposta fake parecida com a de httpx."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp
 
 
# ====================================================================
# POST /deletar-pokemon/{pokemon_id}  -> 200
# ====================================================================
class TestDeletarPokemon200:
 
    def test_deleta_pokemon_existente_no_banco(self, client, mock_db):
        pokemon_existente = MagicMock(pokemon_id=25, pokemon_name="pikachu")
 
        # 1ª query -> CadastroPokemon (existe) | 2ª query -> ExclusaoPokemon (não existe)
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            pokemon_existente,
            None,
        ]
 
        with patch(f"{MODULE_PATH}.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            response = client.post("/deletar-pokemon/25")
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon excluido!!"}
 
    def test_deleta_pokemon_via_pokeapi_e_limpa_cache_redis(self, client, mock_db):
        # Não existe no banco (nem em CadastroPokemon nem em ExclusaoPokemon)
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, None]
 
        pokeapi_resp = fake_pokeapi_response(
            status_code=200,
            json_data={"forms": [{"name": "pikachu"}]},
        )
 
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=pokeapi_resp),
        ), patch(f"{MODULE_PATH}.redis_client") as mock_redis:
            mock_redis.get.return_value = "cache-existente"
 
            response = client.post("/deletar-pokemon/25")
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon deletado com sucesso!"}
 
 
# ====================================================================
# POST /cadastrar-pokemon  -> 200
# ====================================================================
class TestCadastrarPokemon200:
 
    payload_valido = {
        "pokemon_name": "Pikachu",
        "pokemon_type": ["electric"],
        "pokemon_height": 4,
        "pokemon_weight": 60,
        "pokemon_sprites": {"front_default": "url_front", "back_default": "url_back"},
    }
 
    def test_cadastra_pokemon_novo_sem_pokemons_no_banco(self, client, mock_db):
        # Não existe na PokeAPI nem no banco
        mock_db.query.return_value.filter.return_value.first.return_value = None
        # order_by().first() -> nenhum pokémon cadastrado ainda
        mock_db.query.return_value.order_by.return_value.first.return_value = None
 
        pokeapi_count_resp = MagicMock(status_code=200)
        pokeapi_count_resp.json.return_value = {"count": 1301}
 
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.get = AsyncMock(return_value=pokeapi_count_resp)
 
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ), patch(f"{MODULE_PATH}.httpx2") as mock_httpx2, patch(
            f"{MODULE_PATH}.redis_client"
        ):
            mock_httpx2.AsyncClient.return_value = mock_async_client
 
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon cadastrado com sucesso!"}
 
    def test_cadastra_pokemon_novo_com_pokemons_existentes_no_banco(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        ultimo_pokemon = MagicMock(pokemon_id=150)
        mock_db.query.return_value.order_by.return_value.first.return_value = ultimo_pokemon
 
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ), patch(f"{MODULE_PATH}.redis_client"):
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon cadastrado com sucesso!"}
 
 
# ====================================================================
# PUT /alterar-pokemon/{pokemon_id}  -> 200
# ====================================================================
class TestAlterarPokemon200:
 
    payload_valido = {"pokemon_name": "raichu"}
 
    def test_atualiza_pokemon_existente_no_banco(self, client, mock_db):
        # Se a sua rota fizer mais de 2 queries, use return_value em vez de side_effect fixo
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        respostas = [
            fake_pokeapi_response(status_code=200, json_data={"id": 25}), # busca por id
            fake_pokeapi_response(status_code=404), # busca por nome -> não existe
        ]
        
        pokemon_atualizado_dict = {"pokemon_id": 25, "pokemon_name": "raichu"}
        
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(side_effect=respostas),
        ), patch(
            f"{MODULE_PATH}.atualizar_pokemon_no_banco_de_dados",
            new=AsyncMock(return_value=pokemon_atualizado_dict),
        ), patch(f"{MODULE_PATH}.redis_client"):
            
            response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 200
 
    def test_cria_pokemon_que_existe_na_pokeapi_mas_nao_no_banco(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None

        pokemon_pokeapi_completo = {
            "id": 25,
            "forms": [{"name": "pikachu"}],
            "height": 4,
            "weight": 60,
            "types": [{"type": {"name": "electric"}}],
            "sprites": {"front_default": "url_front", "back_default": "url_back"},
        }

        respostas = [
            fake_pokeapi_response(status_code=200, json_data=pokemon_pokeapi_completo),
            fake_pokeapi_response(status_code=404),
        ]

        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(side_effect=respostas),
        ), patch(
            f"{MODULE_PATH}.atualizar_pokemon_no_banco_de_dados",
            new=AsyncMock(return_value=None), # Não atualiza
        ), patch(f"{MODULE_PATH}.redis_client"):

            response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 200