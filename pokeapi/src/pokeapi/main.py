from dotenv import load_dotenv
load_dotenv('.env') 
from fastapi import FastAPI
from pokeapi.routers.buscar_pokemon import router as buscar_pokemon 
from pokeapi.services.database.criacao_database import engine, Base
from pokeapi.routers.alterar_deletar_criar_pokemons import router as cadastrar_usuario

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title='PokeAPI - Projeto EBAC',
    description=(
        'API que consulta, cadastra, altera e exclui pokémons, usando a PokeAPI '
        'pública como fonte de dados, com cache em Redis, persistência em banco '
        'relacional e logs de auditoria enviados ao Elasticsearch.'
    ),
    version='1.0.0',
    contact={'name': 'Cauan Penha', 'email': 'cauanppenha@gmail.com'},
)

app.include_router(buscar_pokemon)
app.include_router(cadastrar_usuario)
