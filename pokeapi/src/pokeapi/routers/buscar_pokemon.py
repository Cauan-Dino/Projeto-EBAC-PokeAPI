from fastapi import APIRouter, HTTPException, BackgroundTasks
from pokeapi.services.redis_cache.redis_config import redis_client
import json
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon, logger


router = APIRouter(tags=['Buscar pokémon'])



# Verifica se a foi adicionado algum novo pokémon na PokeAPI
async def verificar_mudanca_pokemons_pokeapi(url: str, limit: int, offset: int, paramentro_origem_da_funcao_log: str | None = None):
    try:
        
        async with httpx2.AsyncClient() as client: # Abre uma conexão com a url e fecha automaticamente a conexão
            response = await client.get(url) # Realiza requisição no endpoint da PokeAPI colocando em background
            
            if response.status_code == 200: 
                response_json = response.json()
                
                # Adiciona a paginação no redis
                paginacao = {
                    'data': response_json['results'],
                    'pagination': {
                        'limit': limit,
                        'offset': offset,
                        'next': response_json['next'],
                        'previous': response_json['previous'],
                        'count': response_json['count']
                    }
                }

                # Salva no redis a paginação
                redis_client.set(name=url, value=json.dumps(paginacao), ex=900)
               
                # Registra no Elasticsearch que a requisição foi um Sucesso
                await registrar_log_de_buscar_pokemon(credencias=None, offset=offset, limit=limit, origem=paramentro_origem_da_funcao_log, endpoint=url, status='success') 
               
                return paginacao 
            
            if response.status_code != 200:
                await registrar_log_de_buscar_pokemon(credencias=None, offset=offset, limit=limit, origem='requisição', endpoint=url, status='failed')
                raise HTTPException(status_code=502, detail='Erro ao consultar a PokeAPI!')
    
    except HTTPException:
        raise 

    except Exception as e:
        logger.error(f'Erro ao conectar com a PokeAPI: {e}') # Envia pro app.log o ERROR 
        # Registra no log o erro ocorrido ao fazer a requisição no endpoint PokeAPI
        await registrar_log_de_buscar_pokemon(credencias=None, offset=offset, limit=limit, origem=paramentro_origem_da_funcao_log, endpoint=url, status='failed') 
        raise HTTPException(status_code=503, detail='Erro ao conectar com a PokeAPI!')





# Busca todos os pokémons
@router.get('/pokemons')
async def buscar_todos_pokemons(
    background: BackgroundTasks,
    limit: int = 20,
    offset: int = 0 
    ):
    if limit < 1 or offset < 0:
        raise HTTPException(
            status_code=400,
            detail='Limit ou offset inválidos!'
        )

    key = f'https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}' # Chave do redis
    
    # Tratamento de erro conexão com o Redis
    try:
        cache = redis_client.get(key) # Pega o valor da chave do redis
    except Exception as e:
        logger.error(f'Erro ao se conectar com o redis: {e}')
        cache = None

    # Retorna o cache se existir
    if cache:
        background.add_task(verificar_mudanca_pokemons_pokeapi,key,limit,offset,'cache') # Adiciona em background o cache
        return json.loads(cache)
    
    # Retorna a paginação caso não exista no redis
    return await verificar_mudanca_pokemons_pokeapi(url=key, limit=limit, offset=offset, paramentro_origem_da_funcao_log='requisição')
    




# Busca um pokémon específico
@router.get('/pokemons/{pokemon_id}')
async def buscar_pokemon_especifico(
    pokemon_id: int
    ):
    URL = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/'

    # Tratamento de erro conexão com o Redis
    try:
        cache = redis_client.get(URL)
    except Exception as e:
        logger.error(f'Erro ao se conectar com o redis: {e}')
        cache = None

    if cache:
        await registrar_log_de_buscar_pokemon(credencias=None, offset=None, limit= None, origem='cache', endpoint=URL, status='success')
        return json.loads(cache)
    
    # Requisita na URL da PokeAPI
    async with httpx2.AsyncClient() as client:
        try:
            response = await client.get(url=URL)
        except httpx2.RequestError as e:
            logger.error(f'Erro ao conectar com a PokeAPI: {e}') # Envia log de ERROR pro app.log
            await registrar_log_de_buscar_pokemon(credencias=None, offset=None, limit=None, origem='requisição', endpoint=URL, status='failed') # Envia log pro Elasticsearch
            raise HTTPException(status_code=503, detail='PokeAPI indisponível no momento!')
    
        # Verifica se o pokemon existe
        if response.status_code == 404:
            await registrar_log_de_buscar_pokemon(credencias=None, offset=None, limit=None, origem='requisição', endpoint=URL, status='failed')
            raise HTTPException(status_code=404,detail=f'Pokémon com id {pokemon_id} não encontrado')
        
        # Verifica se api responde corretamente
        if response.status_code != 200:
            await registrar_log_de_buscar_pokemon(credencias=None, offset=None, limit= None, origem='requisição', endpoint=URL, status='failed')
            raise HTTPException(status_code=502, detail='Erro ao consultar a PokeAPI!')
    
        response_json = response.json() # Pega o json da requisição do endpoint
        

    formatacao = {
        'name': response_json['forms'][0]['name'],
        'id': response_json['id'],
        'height': response_json['height'],
        'weight': response_json['weight'],
        'types': [
            i['type']['name'] for i in response_json['types']
        ],
        'sprites': {
            'front_default': response_json['sprites']['front_default'],
            'back_default': response_json['sprites']['back_default']
        }
        
    }

    redis_client.set(name=URL,value=json.dumps(formatacao),ex=3600) # Salva no redis formatação

    # Registra no log que a requisição foi um sucesso e foi via json do endpoint da PokeAPI 
    await registrar_log_de_buscar_pokemon(credencias=None, offset=None, limit= None, origem='requisição', endpoint=URL, status='success')

    return formatacao

