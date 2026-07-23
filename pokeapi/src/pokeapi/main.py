from dotenv import load_dotenv
load_dotenv('.env') # Remover em produção
from fastapi import FastAPI
from pokeapi.routers.buscar_pokemon import router as buscar_pokemon 
from pokeapi.services.database.criacao_database import engine, Base
from pokeapi.routers.alterar_deletar_criar_pokemons import router as cadastrar_usuario

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(buscar_pokemon)
app.include_router(cadastrar_usuario)