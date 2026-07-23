from pydantic import BaseModel
from typing import List, Dict

class InserirInformacoesPokemon(BaseModel):
    pokemon_name: str 
    pokemon_type: List[str] # Garante que o usuário envie uma lista de strings, ex: ["Fogo", "Voador"]
    pokemon_name: str
    pokemon_height: int
    pokemon_weight: int
    pokemon_sprites: Dict[str, str]


class AlterarInformacoesPokemon(BaseModel):
    pokemon_name: str | None = None
    pokemon_type: List[str] | None = None  # Garante que o usuário envie uma lista de strings, ex: ["Fogo", "Voador"]
    pokemon_height: int | None = None
    pokemon_weight: int | None = None
    pokemon_sprites: Dict[str, str] | None = None 

