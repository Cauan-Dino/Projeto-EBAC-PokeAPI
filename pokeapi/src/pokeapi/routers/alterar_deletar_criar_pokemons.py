from pokeapi.services.database.criacao_database import sessao_db
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pokeapi.services.database.models import CadastroPokemon
import json
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon
from pokeapi.services.redis_cache.redis_config import redis_client
from pokeapi.services.redis_cache.cache_keys import chave_pokemon
from pokeapi.schemas.schema_alterar_criar_pokemons import (
    InserirInformacoesPokemon,
    AlterarInformacoesPokemon,
    MensagemResponse,
    ErroResponse,
)
from pokeapi.services.pokemon_service.requisicao_pokeapi import buscar_pokemon_na_pokeapi, atualizar_pokemon_no_banco_de_dados
from pokeapi.services.pokemon_service.formatador import formatar_pokemon_da_pokeapi, pokemon_orm_para_dict

router = APIRouter(tags=['Altera Características do Pokémon'])


# Endpoint que deleta logicamente um pokémon
@router.delete(
    '/deletar-pokemon/{pokemon_id}',
    response_model=MensagemResponse,
    status_code=200,
    summary='Exclui logicamente um pokémon',
    description=(
        'Marca um pokémon como excluído (soft delete). Se o pokémon ainda não estiver '
        'cadastrado no banco, ele é buscado na PokeAPI e criado já como excluído, para '
        'que fique registrado que aquele id não deve mais ser retornado.'
    ),
    responses={
        400: {'model': ErroResponse, 'description': 'pokemon_id inválido ou pokémon já excluído'},
        404: {'model': ErroResponse, 'description': 'Pokémon não existe na PokeAPI'},
        502: {'model': ErroResponse, 'description': 'Erro ao consultar a PokeAPI'},
    },
)
async def deletar_pokemon(
    request: Request,
    pokemon_id: int, 
    db: Session = Depends(sessao_db)
    ):
    # Variaveis que serão enviadas pro log. Se algo mudar as variaveis mudam também
    log_status = 'success'
    log_motivo = 'Pokémon excluído com sucesso'
    log_endpoint_str = f'{request.method} {request.url.path}'
    log_origem = 'endpoint:/deletar-pokemon'

    try:
        if pokemon_id < 1:
            log_status = 'failed'
            log_motivo = 'pokemon_id menor que 1'
            raise HTTPException(
                status_code=400,
                detail='Não pode inserir um pokemon_id abaixo de 1!'
            )

        pokemon_no_banco = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == pokemon_id).first()

        if pokemon_no_banco and pokemon_no_banco.pokemon_excluido:
            log_status = 'failed'
            log_motivo = 'Pokémon já foi excluido'
            log_origem = 'banco de dados:query no banco de dados'
            raise HTTPException(
                status_code=400,
                detail='Pokémon já está excluido!'
            )

        cache_key = chave_pokemon(pokemon_id)

        # Exclui logicamente o pokémon que já está cadastrado
        if pokemon_no_banco:
            log_origem = 'banco de dados: query no banco de dados'

            pokemon_no_banco.pokemon_excluido = True
            db.commit()

            try:
                if redis_client.exists(cache_key):
                    redis_client.delete(cache_key)
            except Exception as e:
                print(f"[AVISO] Erro ao limpar cache no Redis: {e}")

            return {'message': 'Pokémon excluido!!'}

        # Pokémon não está no banco: busca na PokeAPI pra confirmar que existe
        requisicao_pokeapi = await buscar_pokemon_na_pokeapi(id_pokemon=pokemon_id)
        
        if requisicao_pokeapi.status_code == 404:
            log_motivo = f'pokemon {pokemon_id} não existe'
            log_status = 'failed'
            
            raise HTTPException(
                status_code=404,
                detail='Esse pokémon não existe!'
            )
        
        if requisicao_pokeapi.status_code != 200:
            log_motivo = f'Erro PokeAPI (Status {requisicao_pokeapi.status_code})'
            log_status = 'failed'

            raise HTTPException(
                status_code=502,
                detail='Erro ao consultar a PokeAPI!'
            )

        # Cria o registro já marcado como excluído, pra manter o histórico
        # de que esse id foi excluído (mesmo nunca tendo sido cadastrado antes)
        dados_pokemon = formatar_pokemon_da_pokeapi(requisicao_pokeapi.json())
        excluir_pokemon = CadastroPokemon(**dados_pokemon, pokemon_excluido=True)

        db.add(excluir_pokemon)
        db.commit()
        db.refresh(excluir_pokemon)

        # Exclui o pokémon salvo no Redis SE EXISTIR (chave padronizada)
        try:
            if redis_client.exists(cache_key):
                redis_client.delete(cache_key)
        except Exception as e:
            print(f"[AVISO] Erro ao limpar cache no Redis: {e}")

        return {'message':'Pokémon deletado com sucesso!'}
    
    except HTTPException:
        # Captura as HTTPException do fastapi
        raise 

    except Exception as e:
        # Captura apenas bugs não previsto (KeyError, ZeroDivisionError, etc)
        log_motivo = f'Ocorreu um erro: {e}'
        log_status = 'error'
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro interno no servidor")
    
    finally:
        try:
            await registrar_log_de_buscar_pokemon(
            offset=None,
            limit=None,
            origem=log_origem,
            motivo=log_motivo,
            endpoint=log_endpoint_str,
            status=log_status
            )
        except Exception as e:
            # Captura o erro se o Elasticsearch não estiver acessível,
            print(f"[AVISO] Elasticsearch offline/indisponível: {e}")


# Endpoint que cadastra um pokémon
@router.post(
    '/cadastrar-pokemon',
    response_model=MensagemResponse,
    status_code=201,
    summary='Cadastra um novo pokémon',
    description='Cadastra um pokémon manualmente, desde que o nome ainda não exista na PokeAPI nem no banco.',
    responses={
        400: {'model': ErroResponse, 'description': 'Pokémon já existe (na PokeAPI ou no banco) / erro ao consultar a PokeAPI'},
    },
)
async def cadastrar_pokemon(
    body: InserirInformacoesPokemon,
    request: Request,
    db: Session = Depends(sessao_db)
    ):
    # Variaveis que serão enviadas pro log. Se algo mudar as variaveis mudam também
    log_status = 'success'
    log_motivo = 'Pokémon cadastrado com sucesso'
    log_endpoint_str = f'{request.method} {request.url.path}'
    log_origem = 'endpoint:/cadastrar-pokemon'
    
    try:
        # Deixa minusculo o nome do pokemon Pra evitar erros na requisição da PokeAPI
        body.pokemon_name = body.pokemon_name.lower()

        # Faz uma requisição na PokeAPI
        requisicao_pokeapi = await buscar_pokemon_na_pokeapi(nome_pokemon=body.pokemon_name)

        # Verifica se esse pokémon existe na PokeAPI ou no banco de dados
        if requisicao_pokeapi.status_code == 200 or db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_name == body.pokemon_name).first():
            log_status = 'failed'
            log_motivo = 'Esse pokémon já existe'

            raise HTTPException(
                status_code=400,
                detail='Esse pokémon já existe!'
            )
        
        # ------ Pega quantos Pokémons tem cadastrado -------
        
        # Pega o maior id do pokemon no banco de dados SE HOUVER
        ultimo_pokemon = db.query(CadastroPokemon).order_by(desc(CadastroPokemon.pokemon_id)).first()
        if ultimo_pokemon is None:
            # Faz uma requisição na PokeAPI pra pegar a quantidade de Pokémons cadastrados
            async with httpx2.AsyncClient() as client:
                response = await client.get('https://pokeapi.co/api/v2/pokemon/')

                # Mensagem de erro se a api não respondeu corretamente
                if response.status_code != 200:
                    log_motivo = f'Ocorreu um erro ao tentar se comunicar com a PokeAPI: {response.status_code}'
                    log_status = 'failed'
                    log_origem = 'https://pokeapi.co/api/v2/pokemon/'
                    
                    raise HTTPException(
                        status_code=400,
                        detail='Ocorreu um erro ao tentar cadastrar o pokémon!'
                    )
                
            quantidade_pokemons_cadastrados = response.json()['count'] + 1
        
        else:
            quantidade_pokemons_cadastrados = ultimo_pokemon.pokemon_id + 1 

        # --------------------------------------------------- 
        

        adicionar_pokemon = CadastroPokemon(pokemon_id=quantidade_pokemons_cadastrados, **body.model_dump())
        db.add(adicionar_pokemon)
        db.commit()
        db.refresh(adicionar_pokemon)

        redis_client.set(
            name=chave_pokemon(quantidade_pokemons_cadastrados),
            value=json.dumps(pokemon_orm_para_dict(adicionar_pokemon)),
        )

        return {'message':'Pokémon cadastrado com sucesso!'}
    
    except HTTPException:
        # Captura as HTTPException do fastapi
        raise 

    except Exception as e:
        # Captura apenas bugs não previsto (KeyError, ZeroDivisionError, etc)
        log_motivo = f'Ocorreu um erro: {e}'
        log_status = 'error'
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro interno no servidor")

    finally:
        try:
            await registrar_log_de_buscar_pokemon(
            offset=None,
            limit=None,
            origem=log_origem,
            motivo=log_motivo,
            endpoint=log_endpoint_str,
            status=log_status
            )
        except Exception as e:
            # Captura o erro se o Elasticsearch não estiver acessível,
            print(f"[AVISO] Elasticsearch offline/indisponível: {e}")


# Altera as características do pokémon
@router.put(
    '/alterar-pokemon/{pokemon_id}',
    response_model=MensagemResponse,
    summary='Altera as características de um pokémon',
    description='Atualiza (parcialmente) os dados de um pokémon já cadastrado, ou cria um novo registro se ele existir na PokeAPI mas não no banco.',
    responses={
        400: {'model': ErroResponse, 'description': 'Pokémon excluído, nome já em uso, ou pokémon não existe'},
        500: {'model': ErroResponse, 'description': 'Erro ao consultar a PokeAPI'},
    },
)
async def alterar_caracteristicas_pokemon(
    body: AlterarInformacoesPokemon,
    pokemon_id: int,
    request: Request,
    db: Session = Depends(sessao_db)
    ):
    # Variaveis que serão enviadas pro log. Se algo mudar as variaveis mudam também
    log_status = 'success'
    log_motivo = f'Informações do pokémon {pokemon_id} alteradas com sucesso'
    log_endpoint_str = f'{request.method} {request.url.path}'
    log_origem = f'endpoint:/alterar-pokemon/{pokemon_id}'
    
    try:
        pokemon_esta_excluido = db.query(CadastroPokemon).filter(
            CadastroPokemon.pokemon_id == pokemon_id,
            CadastroPokemon.pokemon_excluido == True,  # noqa: E712
        ).first()
        if pokemon_esta_excluido:
            log_status = 'failed'
            log_motivo = 'pokémon está excluido'
            log_origem = f'banco de dados: query no banco de dados'

            raise HTTPException(
                status_code=400,
                detail='Pokémon está excluido!'
            )

        if body.pokemon_name:
            nome_do_pokemon_cadastrado = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_name == body.pokemon_name).first()
            if nome_do_pokemon_cadastrado:
                log_motivo = 'nome do pokemon já existe no banco de dados'
                log_origem = 'banco de dados: query no banco de dados'
                log_status = 'failed'

                raise HTTPException(
                    status_code=400,
                    detail='Esse nome já existe no banco de dados!'
                )

        id_do_pokemon_cadastrado = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == pokemon_id).first()    
        if id_do_pokemon_cadastrado:
            pokemon_atualizado = await atualizar_pokemon_no_banco_de_dados(
                pokemon_id=pokemon_id,
                db=db,
                dados=body,
                Tabela_Banco_de_dados=CadastroPokemon
            )
        
            if pokemon_atualizado:
                log_motivo = 'pokémon atualizado com sucesso no banco de dados'
                log_origem = 'banco de dados: pokemon atualizado'

                # Atualiza o redis com o registro COMPLETO e já padronizado
                redis_client.set(
                    name=chave_pokemon(pokemon_id),
                    value=json.dumps(pokemon_orm_para_dict(pokemon_atualizado)),
                )

                return {'message': f'Pokémon {pokemon_id} atualizado com sucesso!'}


        # ---- Verifica se o pokémon existe na PokeAPI -------------------

        existe_pokemon_na_pokeapi = await buscar_pokemon_na_pokeapi(id_pokemon=pokemon_id)
        # Verifica se o pokemon existe na PokeAPI
        if existe_pokemon_na_pokeapi.status_code == 404:
            log_origem = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'
            log_motivo = 'pokémon não existe na pokeapi'
            log_status = 'failed'

            raise HTTPException(
                status_code=400,
                detail=f'Pokémon {pokemon_id} não existe!'
            )
        
        # Verifica se o NOME do pokemon existe na PokeAPI
        if body.pokemon_name:
            response_pokeapi = await buscar_pokemon_na_pokeapi(nome_pokemon=body.pokemon_name)
            if response_pokeapi.status_code == 200 and response_pokeapi.json()['forms'][0]['name'] == body.pokemon_name:
                log_motivo = 'nome do pokemon já existe na PokeAPI'
                log_origem = f'endpoint:https://pokeapi.co/api/v2/pokemon/{body.pokemon_name}'
                log_status = 'failed'

                raise HTTPException(
                    status_code=400,
                    detail='Esse nome de pokémon já existe na PokeAPI'
                )

        # ----------------------------------------------------------------

        if existe_pokemon_na_pokeapi.status_code != 200:
            log_origem = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'
            log_motivo = f'Ocorreu um erro {existe_pokemon_na_pokeapi.status_code}'
            log_status = 'failed'

            raise HTTPException(
                status_code=500,
                detail=f'Ocorreu um erro ao tentar se comunicar com a PokeAPI!'
            )
        
        # Adiciona NOVAS informações de um Pokémon que já existe na PokeAPI e SALVA no Banco de Dados 
        else:
            formatacao = formatar_pokemon_da_pokeapi(existe_pokemon_na_pokeapi.json())

            # Pega apenas os campos enviados na requisição
            dados_para_atualizar = body.model_dump(exclude_unset=True)

            # Os valores de 'dados_para_atualizar' sobrescrevem os de 'formatacao'
            dados_finais = formatacao | dados_para_atualizar

            pokemon = CadastroPokemon(**dados_finais)
            db.add(pokemon)
            db.commit()
            db.refresh(pokemon)

            redis_client.set(name=chave_pokemon(pokemon_id), value=json.dumps(pokemon_orm_para_dict(pokemon)))

            log_origem = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/'
            log_motivo = f'pokémon alterado com sucesso (existente na pokeapi, mas não no banco de dados). Pokemon_id: {pokemon_id}'

            return {'message': f'Pokémon {pokemon_id} atualizado com sucesso!'}

        
    except HTTPException:
        # Captura apenas erros HTTPException no FastAPI
        raise 

    except Exception as e:
        # Captura apenas bugs não previsto (KeyError, ZeroDivisionError, etc)
        log_motivo = f'Ocorreu um erro: {e}'
        log_status = 'error'
        db.rollback()
        raise HTTPException(status_code=500,detail='Erro no servidor!')

    finally:
        try:
            await registrar_log_de_buscar_pokemon(
            offset=None,
            limit=None,
            origem=log_origem,
            motivo=log_motivo,
            endpoint=log_endpoint_str,
            status=log_status
            )
        except Exception as e:
            # Captura o erro se o Elasticsearch não estiver acessível,
            print(f"[AVISO] Elasticsearch offline/indisponível: {e}")
