from pokeapi.services.database.criacao_database import sessao_db
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pokeapi.services.database.models import ExclusaoPokemon, CadastroPokemon
import json
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx2
from pokeapi.log.logs_settings import registrar_log_de_buscar_pokemon
from pokeapi.services.redis_cache.redis_config import redis_client
from pokeapi.schemas.schema_alterar_criar_pokemons import InserirInformacoesPokemon, AlterarInformacoesPokemon
from pokeapi.services.pokemon_service.requisicao_pokeapi import buscar_pokemon_na_pokeapi, atualizar_pokemon_no_banco_de_dados

router = APIRouter(tags=['Altera Características do Pokémon'])



# Endpoint que deleta logicamente um pokémon
@router.post('/deletar-pokemon/{pokemon_id}')
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
        
        pokemon_existe = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_id == pokemon_id).first()

        pokemon_excluido = db.query(ExclusaoPokemon).filter(ExclusaoPokemon.pokemon_id == pokemon_id).first()
        
        # Exclui logicamente o pokémon
        if pokemon_existe and pokemon_excluido is None:
            log_origem = 'banco de dados: query no banco de dados'
            
            excluir_pokemon_logicamente = ExclusaoPokemon(
                pokemon_id=pokemon_existe.pokemon_id, 
                pokemon_nome=pokemon_existe.pokemon_name
            )
            db.add(excluir_pokemon_logicamente)
            db.commit()
            db.refresh(excluir_pokemon_logicamente)

            return {'message':'Pokémon excluido!!'}
        
        # Exibe mensagem de erro se o pokémon já estiver sido excluido
        elif pokemon_excluido:
            log_status = 'failed'
            log_motivo = 'Pokémon já foi excluido'
            log_origem = 'banco de dados:query no banco de dados'

            raise HTTPException(
                status_code=400,
                detail='Pokémon já está excluido!'
            )

        # Faz uma requisição na PokeAPI
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

        # Exclui o pokemon logicamente
        excluir_pokemon = ExclusaoPokemon(
            pokemon_id=pokemon_id, 
            pokemon_nome=requisicao_pokeapi.json()['forms'][0]['name'] # Nome do pokémon
        )

        db.add(excluir_pokemon)
        db.commit()
        db.refresh(excluir_pokemon)

        # Exclui o pokémon salvo no Redis SE EXISTIR
        pokemon_no_cache = redis_client.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}')
        if pokemon_no_cache:
            redis_client.delete(pokemon_no_cache)

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
@router.post('/cadastrar-pokemon')
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

        dados_cache = body.model_dump()
        dados_cache["id"] = quantidade_pokemons_cadastrados

        # Adiciona no Cache Permanentemente
        redis_client.set(name=f'https://pokeapi.co/api/v2/pokemon/{quantidade_pokemons_cadastrados}/', value=json.dumps(dados_cache))

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
@router.put('/alterar-pokemon/{pokemon_id}')
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
        id_pokemon_excluido = db.query(ExclusaoPokemon).filter(ExclusaoPokemon.pokemon_id == pokemon_id).first()
        if id_pokemon_excluido:
            log_status = 'failed'
            log_motivo = 'pokémon está excluido'
            log_origem = f'banco de dados: query no banco de dados'

            raise HTTPException(
                status_code=400,
                detail='Pokémon está excluido!'
            )

        nome_do_pokemon_cadastrado = db.query(CadastroPokemon).filter(CadastroPokemon.pokemon_name == body.pokemon_name).first()
        if nome_do_pokemon_cadastrado:
            log_motivo = 'nome do pokemon já existe no banco de dados'
            log_origem = 'banco de dados: query no banco de dados'
            log_status = 'failed'

            raise HTTPException(
                status_code=400,
                detail='Esse nome já existe no banco de dados!'
            )

        id_do_pokemon_cadastrado = db.query(CadastroPokemon.pokemon_id == pokemon_id).first()    
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

                # Atualiza o redis
                redis_client.set(name=f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/', value=json.dumps(pokemon_atualizado)) # Pega o dicionario atualizado

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

        pokemon_atualizado = await atualizar_pokemon_no_banco_de_dados(
            pokemon_id=pokemon_id,
            db=db,
            dados=body,
            Tabela_Banco_de_dados=CadastroPokemon
            )
        
        if pokemon_atualizado:
            log_motivo = 'pokémon atualizado com sucesso no banco de dados'
            log_origem = 'banco de dados: pokemon atualizado'

            # Atualiza o redis
            redis_client.set(name=f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/', value=json.dumps(pokemon_atualizado)) # Pega o dicionario atualizado

            return {'message': f'Pokémon {pokemon_id} atualizado com sucesso!'}


        if existe_pokemon_na_pokeapi.status_code != 200:
            log_origem = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'
            log_motivo = f'Ocorreu um erro {existe_pokemon_na_pokeapi.status_code}'
            log_status = 'failed'

            raise HTTPException(
                status_code=500,
                detail=f'Ocorreu um erro ao tentar se comunicar com a PokeAPI!'
            )
        
        # Adiciona NOVAS informações de um Pokémon que já existe na PokeAPI e SALVA no Banco de Dados 
        elif existe_pokemon_na_pokeapi.status_code == 200:
            formatacao = {
            'pokemon_id': existe_pokemon_na_pokeapi.json()['id'],
            'pokemon_name': existe_pokemon_na_pokeapi.json()['forms'][0]['name'],
            'pokemon_height': existe_pokemon_na_pokeapi.json()['height'],
            'pokemon_weight': existe_pokemon_na_pokeapi.json()['weight'],
            'pokemon_type': [
                i['type']['name'] for i in existe_pokemon_na_pokeapi.json()['types']
            ],
            'pokemon_sprites': {
                'front_default': existe_pokemon_na_pokeapi.json()['sprites']['front_default'],
                'back_default': existe_pokemon_na_pokeapi.json()['sprites']['back_default']
            }
        }

            # Pega apenas os campos enviados na requisição
            dados_para_atualizar = body.model_dump(exclude_unset=True)

            # Os valores de 'dados_para_atualizar' sobrescrevem os de 'formatacao'
            dados_finais = formatacao | dados_para_atualizar

            pokemon = CadastroPokemon(**dados_finais)
            db.add(pokemon)
            db.commit()
            db.refresh(pokemon)

            redis_client.set(name=f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/', value=json.dumps(dados_finais))

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