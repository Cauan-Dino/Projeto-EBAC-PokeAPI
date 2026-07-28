from fastapi import APIRouter, HTTPException, Depends, Request
from pokeapi.services.redis_cache.redis_config import redis_client
from pokeapi.services.redis_cache.cache_keys import chave_pokemon, chave_paginacao
import json
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon, logger
from pokeapi.services.database.criacao_database import sessao_db
from sqlalchemy.orm import Session
from pokeapi.services.database.models import CadastroPokemon
from pokeapi.services.pokemon_service.requisicao_pokeapi import verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache
from pokeapi.services.pokemon_service.formatador import formatar_pokemon_da_pokeapi, pokemon_orm_para_dict
from pokeapi.schemas.schema_alterar_criar_pokemons import PokemonResponse, PokemonPaginadoResponse, ErroResponse


router = APIRouter(tags=['Buscar pokémon'])


# Busca todos os pokémons
@router.get(
    '/pokemons',
    response_model=PokemonPaginadoResponse,
    summary='Lista pokémons paginados',
    description=(
        'Retorna uma página de pokémons vindos da PokeAPI. O resultado fica em cache '
        'no Redis por 15 minutos (900s) para evitar requisições repetidas à PokeAPI.'
    ),
    responses={
        400: {'model': ErroResponse, 'description': 'limit ou offset inválidos'},
        502: {'model': ErroResponse, 'description': 'Erro ao consultar a PokeAPI'},
        503: {'model': ErroResponse, 'description': 'PokeAPI indisponível'},
    },
)
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

        key = chave_paginacao(offset=offset, limit=limit)  # Chave do redis (mesma URL usada na PokeAPI)
        
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
@router.get(
    '/pokemons/{pokemon_id}',
    response_model=PokemonResponse,
    summary='Busca um pokémon específico',
    description=(
        'Busca um pokémon por id, nessa ordem: cache (Redis) → banco de dados → PokeAPI. '
        'Se o pokémon tiver sido excluído logicamente, retorna 400.'
    ),
    responses={
        400: {'model': ErroResponse, 'description': 'Pokémon foi excluído logicamente'},
        404: {'model': ErroResponse, 'description': 'Pokémon não encontrado na PokeAPI'},
        502: {'model': ErroResponse, 'description': 'Erro ao consultar a PokeAPI'},
        503: {'model': ErroResponse, 'description': 'PokeAPI indisponível'},
    },
)
async def buscar_pokemon_especifico(
    pokemon_id: int,
    request: Request,
    db: Session = Depends(sessao_db)
    ):
    URL = chave_pokemon(pokemon_id)
    
    # Log que será enviado pro Elasticsearch caso retorne 200. Se não serão outros valores
    log_status = 'success'
    log_motivo = 'Pokémon retornado com sucesso'
    log_url_endpoint = f'{request.method} {request.url.path}' 
    log_origem = f'endpoint:/pokemons/{pokemon_id}'

    try:
        # Uma única consulta no banco resolve tanto "existe?" quanto "está excluído?",
        # já que agora é a mesma tabela (antes eram duas tabelas/duas queries).
        pokemon_no_banco = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == pokemon_id).first()

        if pokemon_no_banco and pokemon_no_banco.pokemon_excluido:
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
        
        # Se existe no Banco de Dados (e não está excluído), retorna via banco
        if pokemon_no_banco:
            log_motivo = 'pokémon existe no banco de dados'
            log_origem = 'banco de dados:query no banco de dados'

            return pokemon_no_banco
        

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

        # Usa o schema canônico (mesmo formato do banco/cadastro/alteração),
        # em vez do dict ad-hoc {'name','id','height','weight','types','sprites'}
        # que era usado só aqui e destoava do resto da API.
        formatacao = formatar_pokemon_da_pokeapi(response_json)

        redis_client.set(name=URL, value=json.dumps(formatacao), ex=3600) # Salva no redis formatação

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
