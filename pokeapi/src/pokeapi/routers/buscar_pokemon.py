from fastapi import APIRouter, HTTPException, Depends, Request
from pokeapi.services.redis_cache.redis_config import redis_client
import json
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon, logger
from pokeapi.services.database.criacao_database import sessao_db
from sqlalchemy.orm import Session
from pokeapi.services.database.models import ExclusaoPokemon, CadastroPokemon
from pokeapi.services.pokemon_service.requisicao_pokeapi import verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache

router = APIRouter(tags=['Buscar pokémon'])



# Busca todos os pokémons
@router.get('/pokemonsss')
async def buscar_todos_pokemons(
    request: Request,
    limit: int = 20,
    offset: int = 0
    ):
    # Log que será enviado pro Elasticsearch caso retorne 200. Se não serão outros valores
    log_status = 'success'
    log_motivo = 'Pokémons retornados com sucesso'
    log_url_endpoint = f'{request.method} {request.url.path}' 
    log_origem = f'endpoint:/pokemons'

    try:
        if limit < 1 or offset < 0:
            log_motivo = 'Limite abaixo de 1 ou offset abaixo de 0'
            log_status = 'failed'

            raise HTTPException(
                status_code=400,
                detail='Limit ou offset inválidos!'
            )

        key = f'https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}' # Chave do redis
        
        try:
            cache = redis_client.get(key) # Pega o valor da chave do redis
        except Exception as e:
            logger.error(f'Erro ao se conectar com o redis: {e}')
            cache = None
        
        if cache:
            log_motivo = 'Pokémons retornados com sucesso via redis'
            log_origem = 'cache'
            
            return json.loads(cache)
        
        # Retorna a paginação caso não exista no redis
        return await verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache(request=request, url=key, limit=limit, offset=offset)
    
    except HTTPException:
        # Captura apenas Erros HTTPException do FastAPI
        raise 

    except Exception as e:
        # Captura erros não previstos como (KeyError, ZeroDivisionError, etc)
        log_status = 'error'
        log_motivo = f'Ocorreu um erro: {e}'
        raise HTTPException(status_code=500, detail="Erro interno no servidor")

    finally:
        try:
            await registrar_log_de_buscar_pokemon(
            offset=None,
            limit=None,
            origem=log_origem,
            motivo=log_motivo,
            endpoint=log_url_endpoint,
            status=log_status
            )
        except Exception as e:
            # Captura o erro se o Elasticsearch não estiver acessível,
            print(f"[AVISO] Elasticsearch offline/indisponível: {e}")

    




# Busca um pokémon específico
@router.get('/pokemons/{pokemon_id}')
async def buscar_pokemon_especifico(
    pokemon_id: int,
    request: Request,
    db: Session = Depends(sessao_db)
    ):
    URL = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/'
    
    # Log que será enviado pro Elasticsearch caso retorne 200. Se não serão outros valores
    log_status = 'success'
    log_motivo = 'Pokémon retornado com sucesso'
    log_url_endpoint = f'{request.method} {request.url.path}' 
    log_origem = f'endpoint:/pokemons/{pokemon_id}'

    try:
        # Se a query for TRUE, o pokémon está excluido
        pokemon_esta_excluido = db.query(ExclusaoPokemon).filter(ExclusaoPokemon.pokemon_id == pokemon_id).first()
        if pokemon_esta_excluido:
            log_status = 'failed'
            log_origem = 'banco de dados:query no banco de dados'
            log_motivo = 'pokémon já está excluido'

            raise HTTPException(
                status_code=400,
                detail='Pokémon está excluido!'
            )

        try:
            cache = redis_client.get(URL)
        except Exception as e:
            logger.error(f'Erro ao se conectar com o redis: {e}')
            cache = None

        if cache:
            log_status = 'success'
            log_motivo = 'Pokémon retornado com sucesso via cache'
            log_origem = 'cache'
            return json.loads(cache)
        
        
        # Se a query for TRUE, o pokémon existe no Banco de Dados (RETORNA VIA BANCO DE DADOS)
        pokemon_existe_no_db = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == pokemon_id).first()
        if pokemon_existe_no_db:
            log_motivo = 'pokémon existe no banco de dados'
            log_origem = 'banco de dados:query no banco de dados'

            return pokemon_existe_no_db
        

        # ------ Requisição na URL da PokeAPI ----------------------
        
        async with httpx2.AsyncClient() as client:
            try:
                response = await client.get(url=URL)
            except httpx2.RequestError as e:
                logger.error(f'Erro ao conectar com a PokeAPI: {e}') # Envia log de ERROR pro app.log
                
                log_status = 'failed'
                log_motivo = f'Erro ao tentar se conectar com a PokeAPI: {e}'
                log_url_origem = f'endpoint:{URL}'

                raise HTTPException(status_code=503, detail='PokeAPI indisponível no momento!')
        
            if response.status_code == 404:
                log_status = 'failed'
                log_motivo = f'Pokémon {pokemon_id} não existe'
                log_url_origem = f'endpoint:{URL}'
                
                raise HTTPException(status_code=404,detail=f'Pokémon com id {pokemon_id} não encontrado')
            
            if response.status_code != 200:
                log_status = 'failed'
                log_motivo = f'Erro ao tentar se conectar com a PokeAPI: {response.status_code}'
                log_url_origem = f'endpoint:{URL}'

                raise HTTPException(status_code=502, detail='Erro ao consultar a PokeAPI!')
        
        response_json = response.json() # Pega o json da requisição do endpoint
        
        # ----------------------------------------------------------

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

        return formatacao
    
    except HTTPException:
        # Captura as HTTPException do fastapi
        raise 

    except Exception as e:
        # Captura apenas bugs não previsto (KeyError, ZeroDivisionError, etc)
        log_motivo = f'Ocorreu um erro: {e}'
        log_status = 'error'
        raise HTTPException(status_code=500, detail="Erro interno no servidor")

    finally:
        try:
            await registrar_log_de_buscar_pokemon(
            offset=None,
            limit=None,
            origem=log_origem,
            motivo=log_motivo,
            endpoint=log_url_endpoint,
            status=log_status
            )
        except Exception as e:
            # Captura o erro se o Elasticsearch não estiver acessível,
            print(f"[AVISO] Elasticsearch offline/indisponível: {e}")




