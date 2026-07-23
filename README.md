# PokeAPI

Projeto final do curso de Python/FastAPI da EBAC: uma API que consulta, cadastra, altera e exclui (logicamente) pokémons, integrando com a [PokeAPI](https://pokeapi.co/) pública, usando Redis como camada de cache e um stack ELK (Elasticsearch, Logstash, Kibana) para observabilidade dos logs.

---

## Descrição

A API expõe endpoints para:

- Buscar todos os pokémons (com paginação) ou um pokémon específico, com cache em Redis.
- Cadastrar um novo pokémon no banco de dados.
- Alterar as características de um pokémon já cadastrado.
- Excluir logicamente um pokémon (exclusão via tabela própria, sem apagar o registro original).

Todas as ações geram logs estruturados enviados para o Elasticsearch, permitindo acompanhar sucesso, falhas e origem (cache, banco de dados ou PokeAPI) de cada requisição.

---

## Link

- `https://projeto-ebac-pokeapi.onrender.com/docs` -> Documentação Swagger
- `https://projeto-ebac-pokeapi.onrender.com` -> Link da API

---

### Principais tecnologias

- **FastAPI** — framework da API
- **SQLAlchemy** — persistência (cadastro e exclusão lógica de pokémons)
- **Redis** — cache das respostas
- **Elasticsearch / Logstash / Kibana (ELK)** — logging e observabilidade
- **httpx2** — cliente HTTP assíncrono para consumir a PokeAPI
- **Pytest + pytest-mock** — testes automatizados
- **Podman Compose** — orquestração dos containers

---

## Como rodar localmente

1. Clone o repositório:
   ```bash
   git clone <url-do-repositorio>
   cd pokeapi
   ```

2. Crie um arquivo `.env` na raiz do projeto com as variáveis necessárias, por exemplo:
   ```env
  REDIS_HOST=redis
  REDIS_PORT=6379
  LOG_FILE_PATH=/logs/app.log
  ES_HOST=elasticsearch
  ES_PORT=9200
  KIBANA_PORT=5601
  URL_DB=sqlite:///pokeapi.db
   ```

3. Suba os containers (Redis, Elasticsearch/Kibana e a própria API) com Podman Compose:
   ```bash
   podman-compose up --build -d
   ```

4. Com a API no ar, acesse a documentação interativa (Swagger UI) em:
   ```
   http://localhost:8000/docs
   ```

## Como executar os testes

Os testes usam `pytest` com `pytest-mock` para mockar chamadas à PokeAPI, ao Redis e à sessão do banco de dados (evitando dependência de serviços externos durante a execução).

```bash
# Instala as dependências de desenvolvimento, se ainda não tiver
pip install -r requirements.txt

# Roda todos os testes
pytest

# Roda com mais detalhes
pytest -v

# Roda um arquivo específico
pytest tests/test_buscar_pokemon.py
```

## Estrutura de logs

Cada requisição gera um log com `status`, `motivo` (mensagem descritiva), `origem` (cache, banco de dados ou PokeAPI) e o endpoint acessado, enviado para o Elasticsearch e consultável via Kibana.

# log/logs

### logs/logs_settings.py

- Cria a conexão com o elasticsearch pra enviar as logs

### logs/logging.yaml

- Configura o handler, formatters e loggers

---

# routers

## routers/alterar_deletar_criar_pokemons.py

### POST /cadastrar-pokemon

Cadastra um novo pokémon no banco de dados (apenas se ele não existir na PokeAPI nem já estiver cadastrado).

**Requisição**
```
POST /cadastrar-pokemon
Content-Type: application/json
```
```json
{
  "pokemon_name": "meupokemon",
  "pokemon_height": 12,
  "pokemon_weight": 250,
  "pokemon_type": ["grass", "dark"],
  "pokemon_sprites": {
    "front_default": "https://exemplo.com/front.png",
    "back_default": "https://exemplo.com/back.png"
  }
}
```

**Resposta — 200 OK**
```json
{ "message": "Pokémon cadastrado com sucesso!" }
```

**Erros possíveis**
- `400` — o pokémon já existe (na PokeAPI ou no banco)
- `500` — erro interno no servidor

---

### PUT /alterar-pokemon/{pokemon_id}

Altera características de um pokémon já cadastrado. Aceita atualização parcial (só os campos enviados são alterados).

**Requisição**
```
PUT /alterar-pokemon/1
Content-Type: application/json
```
```json
{
  "pokemon_weight": 70
}
```

**Resposta — 200 OK**
```json
{ "message": "Pokémon 1 atualizado com sucesso!" }
```

**Erros possíveis**
- `400` — pokémon excluído, nome já existente, ou pokémon não existe na PokeAPI
- `500` — erro ao se comunicar com a PokeAPI ou erro interno

---

### POST /deletar-pokemon/{pokemon_id}

Exclui logicamente um pokémon (cria um registro na tabela de exclusão, sem apagar o cadastro original).

**Requisição**
```
POST /deletar-pokemon/1
```

**Resposta — 200 OK**
```json
{ "message": "Pokémon excluido!!" }
```

**Erros possíveis**
- `400` — `pokemon_id` menor que 1, ou pokémon já excluído
- `404` — pokémon não existe na PokeAPI
- `502` — erro ao consultar a PokeAPI

## routers/buscar_pokemon.py

### GET /pokemons

Lista os pokémons de forma paginada. Consulta primeiro o Redis; se não houver cache, busca na PokeAPI e salva o resultado.

**Requisição**
```
GET /pokemons?limit=20&offset=0
```

**Resposta — 200 OK**
```json
{
  "data": [
    { "name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon/1/" },
    { "name": "ivysaur", "url": "https://pokeapi.co/api/v2/pokemon/2/" }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "next": "https://pokeapi.co/api/v2/pokemon/?offset=20&limit=20",
    "previous": null,
    "count": 1302
  }
}
```

**Erros possíveis**
- `400` — `limit` menor que 1 ou `offset` negativo
- `502` — erro ao consultar a PokeAPI
- `503` — falha de conexão com a PokeAPI

---

### GET /pokemons/{pokemon_id}

Busca um pokémon específico. Ordem de resolução: exclusão lógica → cache no Redis → banco de dados → PokeAPI.

**Requisição**
```
GET /pokemons/1
```

**Resposta — 200 OK**
```json
{
  "name": "bulbasaur",
  "id": 1,
  "height": 7,
  "weight": 69,
  "types": ["grass", "poison"],
  "sprites": {
    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
    "back_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/1.png"
  }
}
```

**Erros possíveis**
- `400` — pokémon está excluído logicamente
- `404` — pokémon não encontrado na PokeAPI
- `502` — erro ao consultar a PokeAPI
- `503` — falha de conexão com a PokeAPI


---

# schemas

### schemas/schema_alterar_criar_pokemons

- Schemas criados pra passar no json das requisições
    - InserirInformacoesPokemon
        - Utilizado no POST pra cadastrar um pokémon (obrigatório passar todos campos)
    - AlterarInformacoesPokemon
        - Utilizado no PUT pra alterar as informações de um pokémon (não é obrigado a passar todos os paramêntros)

---

# services

## database

### database/criacao_database.py

- Cria o arquivo do banco de dados

### database/models.py

- Cria as tabelas do banco de dados
    - CadastroPokemon
        - Tabela responsável por cadastrar os pokémons (também cadastra as alterações do pokémon)
    - ExclusaoPokemon
        - Tabela que exclui os pokémons, podendo ser do banco de dados e da PokeAPI

## pokemon_service

### pokemon_service/requisicao_pokeapi.py

- verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache
    - Retorna a paginação com os pokemons, limit, offset, next, previous e count. Adiciona no redis a paginação

- buscar_pokemon_na_pokeapi
    - Faz uma requisição na pokeapi, podendo buscar pelo id do pokemon e pelo nome. Retorna o objeto da requisição

- atualizar_pokemon_no_banco_de_dados
    - Atualiza o pokemon no banco de dados e retorna o dicionario com apenas os campos que foram enviados

## redis_cache

### redis_cache/redis_config.py

- Cria o redis e estabelece uma conexão com ele