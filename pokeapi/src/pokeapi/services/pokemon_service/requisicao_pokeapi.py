from fastapi import HTTPException, Request
from pokeapi.services.redis_cache.redis_config import redis_client
import json
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon, logger
from sqlalchemy.orm import Session
from pokeapi.schemas.schema_alterar_criar_pokemons import AlterarInformacoesPokemon

# Verifica se a foi adicionado algum novo pokémon na PokeAPI
async def verificar_mudanca_de_pokemons_pokeapi_e_salva_no_cache(
    request: Request,
    url: str, 
    limit: int, 
    offset: int, 
    ):
    # Log que será enviado pro Elasticsearch caso retorne 200. Se não serão outros valores
    log_motivo = 'Pokémons retornado e salvo no redis com sucesso'
    log_status = 'success'
    log_url_endpoint = f'{request.method} {request.url.path}' 
    log_origem = f'endpoint:{url}'
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

                redis_client.set(name=url, value=json.dumps(paginacao), ex=900)
               
                return paginacao 
            
            if response.status_code != 200:
                log_motivo = f'Ocorreu um erro ao tentar se comunicar com a PokeAPI: {response.status_code}'
                log_status = 'failed'
                log_url_endpoint = f'{request.method} {request.url.path}' 
                log_origem = f'endpoint:{url}'

                raise HTTPException(status_code=502, detail='Erro ao consultar a PokeAPI!')
    
    except HTTPException:
        # Captura apenas erros HTTPException do FastAPI
        raise 

    except Exception as e:
        # Captura apenas bugs não previstos (KeyError, ZeroDivisionError, etc)
        log_motivo = f'Ocorreu um erro: {e}'
        log_status = 'error'
        logger.error(f'Erro ao conectar com a PokeAPI: {e}') # Envia pro app.log o ERROR 
        raise HTTPException(status_code=503, detail='Erro ao conectar com a PokeAPI!')
    
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



# Função que faz uma requisição assíncrona na PokeAPI pra verificar se o pokémon existe
async def buscar_pokemon_na_pokeapi(
    id_pokemon: int | None = None,
    nome_pokemon: str | None = None
    ):
    # Essa variável recebe ou id_pokemono ou nome_pokemon
    paramentro_de_buscar = id_pokemon if id_pokemon is not None else nome_pokemon

    try:
        async with httpx2.AsyncClient() as client:
            response = await client.get(f'https://pokeapi.co/api/v2/pokemon/{paramentro_de_buscar}')
            return response
    
    except Exception as e: 
        logger.error(f'Erro ao conectar com a PokeAPI: {e}')    


# Função que atualiza o pokémon no banco de dados
async def atualizar_pokemon_no_banco_de_dados(
        pokemon_id: int,
        db: Session,
        dados: AlterarInformacoesPokemon,
        Tabela_Banco_de_dados
    ):
    pokemon = db.query(Tabela_Banco_de_dados).filter(Tabela_Banco_de_dados.pokemon_id == pokemon_id).first()
    
    if pokemon:
        # Extrai APENAS os campos enviados explicitamente na requisição
        dados_para_atualizar = dados.model_dump(exclude_unset=True)

        # Atualiza apenas os atributos informados no objeto do banco
        for chave, valor in dados_para_atualizar.items():
            setattr(pokemon, chave, valor)

        db.commit()
        db.refresh(pokemon)
        
        return dados_para_atualizar
