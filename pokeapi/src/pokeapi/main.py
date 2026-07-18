from dotenv import load_dotenv
load_dotenv('.env') # Remover em produção
from fastapi import FastAPI
from pokeapi.routers.buscar_pokemon import router as buscar_pokemon 

app = FastAPI()


app.include_router(buscar_pokemon)