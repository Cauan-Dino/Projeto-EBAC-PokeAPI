

from unittest.mock import MagicMock, AsyncMock, patch
import os
os.environ['URL_DB'] = "sqlite:///./test.db" 
os.environ['ES_HOST'] = 'elasticsearch'
os.environ['ES_PORT'] = '9200'
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
 
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


def fake_pokemon_orm(**kwargs):
    """Monta um objeto que se parece com uma linha ORM de CadastroPokemon."""
    padrao = {
        "pokemon_id": 25,
        "pokemon_name": "pikachu",
        "pokemon_height": 4,
        "pokemon_weight": 60,
        "pokemon_type": ["electric"],
        "pokemon_sprites": {"front_default": "url_front", "back_default": "url_back"},
        "pokemon_excluido": False,
    }
    padrao.update(kwargs)
    return MagicMock(**padrao)

 
# ====================================================================
# DELETE /deletar-pokemon/{pokemon_id}  -> 200
# ====================================================================
class TestDeletarPokemon200:
 
    def test_deleta_pokemon_existente_no_banco(self, client, mock_db):
        pokemon_existente = fake_pokemon_orm(pokemon_excluido=False)

        # Agora é uma única query (uma única tabela, com a flag pokemon_excluido)
        mock_db.query.return_value.filter.return_value.first.return_value = pokemon_existente
 
        with patch(f"{MODULE_PATH}.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            response = client.delete("/deletar-pokemon/25")
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon excluido!!"}
        # A flag deve ter sido marcada como True (soft delete)
        assert pokemon_existente.pokemon_excluido is True
        mock_db.commit.assert_called()
 
    def test_deleta_pokemon_via_pokeapi_e_limpa_cache_redis(self, client, mock_db):
        # Não existe no banco
        mock_db.query.return_value.filter.return_value.first.return_value = None
 
        pokeapi_resp = fake_pokeapi_response(
            status_code=200,
            json_data={
                "id": 25,
                "forms": [{"name": "pikachu"}],
                "height": 4,
                "weight": 60,
                "types": [{"type": {"name": "electric"}}],
                "sprites": {"front_default": "url_front", "back_default": "url_back"},
            },
        )
 
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=pokeapi_resp),
        ), patch(f"{MODULE_PATH}.redis_client") as mock_redis:
            mock_redis.exists.return_value = True
 
            response = client.delete("/deletar-pokemon/25")
 
        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon deletado com sucesso!"}
        # Garante que a chave de cache usada bate com a chave padronizada (com "/" no final)
        mock_redis.delete.assert_called_once_with("https://pokeapi.co/api/v2/pokemon/25/")
        # Garante que o registro criado já nasce marcado como excluído
        criado = mock_db.add.call_args[0][0]
        assert criado.pokemon_excluido is True


# ====================================================================
# DELETE /deletar-pokemon/{pokemon_id}  -> cenários de erro
# ====================================================================
class TestDeletarPokemonErros:

    def test_deletar_pokemon_id_invalido(self, client, mock_db):
        response = client.delete("/deletar-pokemon/0")
        assert response.status_code == 400
        assert "Não pode inserir um pokemon_id abaixo de 1" in response.json()["detail"]

    def test_deletar_pokemon_ja_excluido(self, client, mock_db):
        pokemon_excluido = fake_pokemon_orm(pokemon_excluido=True)
        mock_db.query.return_value.filter.return_value.first.return_value = pokemon_excluido

        response = client.delete("/deletar-pokemon/25")

        assert response.status_code == 400
        assert response.json()["detail"] == "Pokémon já está excluido!"

    def test_deletar_pokemon_nao_existe_na_pokeapi(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ):
            response = client.delete("/deletar-pokemon/999999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Esse pokémon não existe!"

    def test_deletar_pokemon_erro_ao_consultar_pokeapi(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=500)),
        ):
            response = client.delete("/deletar-pokemon/25")

        assert response.status_code == 502
        assert response.json()["detail"] == "Erro ao consultar a PokeAPI!"

    def test_deletar_pokemon_erro_interno_faz_rollback(self, client, mock_db):
        mock_db.query.side_effect = Exception("erro inesperado no banco")

        response = client.delete("/deletar-pokemon/25")

        assert response.status_code == 500
        mock_db.rollback.assert_called_once()
 
 
# ====================================================================
# POST /cadastrar-pokemon  -> 201
# ====================================================================
class TestCadastrarPokemon201:
 
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
        ) as mock_redis:
            mock_httpx2.AsyncClient.return_value = mock_async_client
 
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)
 
        assert response.status_code == 201
        assert response.json() == {"message": "Pokémon cadastrado com sucesso!"}
        # O cache deve ser salvo com a chave padronizada (com "/" no final)
        chave_usada = mock_redis.set.call_args.kwargs["name"]
        assert chave_usada == "https://pokeapi.co/api/v2/pokemon/1302/"
        # E com o schema canônico (prefixo pokemon_*, sem a chave solta "id")
        import json as json_lib
        valor_salvo = json_lib.loads(mock_redis.set.call_args.kwargs["value"])
        assert "pokemon_id" in valor_salvo
        assert "id" not in valor_salvo
 
    def test_cadastra_pokemon_novo_com_pokemons_existentes_no_banco(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        ultimo_pokemon = MagicMock(pokemon_id=150)
        mock_db.query.return_value.order_by.return_value.first.return_value = ultimo_pokemon
 
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ), patch(f"{MODULE_PATH}.redis_client"):
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)
 
        assert response.status_code == 201
        assert response.json() == {"message": "Pokémon cadastrado com sucesso!"}


# ====================================================================
# POST /cadastrar-pokemon  -> cenários de erro
# ====================================================================
class TestCadastrarPokemonErros:

    payload_valido = {
        "pokemon_name": "Pikachu",
        "pokemon_type": ["electric"],
        "pokemon_height": 4,
        "pokemon_weight": 60,
        "pokemon_sprites": {"front_default": "url_front", "back_default": "url_back"},
    }

    def test_cadastrar_pokemon_que_ja_existe_na_pokeapi(self, client, mock_db):
        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=200, json_data={"id": 25})),
        ):
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)

        assert response.status_code == 400
        assert response.json()["detail"] == "Esse pokémon já existe!"

    def test_cadastrar_pokemon_que_ja_existe_no_banco(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = fake_pokemon_orm()

        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ):
            response = client.post("/cadastrar-pokemon", json=self.payload_valido)

        assert response.status_code == 400
        assert response.json()["detail"] == "Esse pokémon já existe!"

    def test_cadastrar_pokemon_payload_invalido(self, client, mock_db):
        payload_invalido = {"pokemon_name": "pikachu"}  # faltam campos obrigatórios

        response = client.post("/cadastrar-pokemon", json=payload_invalido)

        assert response.status_code == 422  # erro de validação do Pydantic
 
 
# ====================================================================
# PUT /alterar-pokemon/{pokemon_id}  -> 200
# ====================================================================
class TestAlterarPokemon200:
 
    payload_valido = {"pokemon_name": "raichu"}
 
    def test_atualiza_pokemon_existente_no_banco(self, client, mock_db):
        # 1ª query: verifica exclusão -> None (não excluído)
        # 2ª query: verifica nome duplicado -> None
        # 3ª query: busca o pokémon a atualizar -> mock "existe"
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None, None, fake_pokemon_orm(),
        ]

        pokemon_atualizado_orm = fake_pokemon_orm(pokemon_name="raichu")
        
        with patch(
            f"{MODULE_PATH}.atualizar_pokemon_no_banco_de_dados",
            new=AsyncMock(return_value=pokemon_atualizado_orm),
        ), patch(f"{MODULE_PATH}.redis_client") as mock_redis:
            
            response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 200
        assert response.json() == {"message": "Pokémon 25 atualizado com sucesso!"}
        # Confirma que o cache foi salvo com o registro COMPLETO (schema canônico)
        import json as json_lib
        valor_salvo = json_lib.loads(mock_redis.set.call_args.kwargs["value"])
        assert valor_salvo["pokemon_name"] == "raichu"
        assert "pokemon_height" in valor_salvo  # campo que não mudou, mas deve continuar presente
 
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
        ), patch(f"{MODULE_PATH}.redis_client"):

            response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 200


# ====================================================================
# PUT /alterar-pokemon/{pokemon_id}  -> cenários de erro
# ====================================================================
class TestAlterarPokemonErros:

    payload_valido = {"pokemon_name": "raichu"}

    def test_alterar_pokemon_excluido(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = fake_pokemon_orm(pokemon_excluido=True)

        response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 400
        assert response.json()["detail"] == "Pokémon está excluido!"

    def test_alterar_pokemon_nome_ja_existe_no_banco(self, client, mock_db):
        # 1ª query (excluído) -> None | 2ª query (nome duplicado) -> encontra
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None, fake_pokemon_orm(pokemon_name="raichu"),
        ]

        response = client.put("/alterar-pokemon/25", json=self.payload_valido)

        assert response.status_code == 400
        assert response.json()["detail"] == "Esse nome já existe no banco de dados!"

    def test_alterar_pokemon_nao_existe_na_pokeapi(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch(
            f"{MODULE_PATH}.buscar_pokemon_na_pokeapi",
            new=AsyncMock(return_value=fake_pokeapi_response(status_code=404)),
        ):
            response = client.put("/alterar-pokemon/999999", json=self.payload_valido)

        assert response.status_code == 400
        assert "não existe" in response.json()["detail"]

    def test_alterar_pokemon_payload_invalido(self, client, mock_db):
        response = client.put("/alterar-pokemon/25", json={"pokemon_height": "não-é-um-numero"})

        assert response.status_code == 422
