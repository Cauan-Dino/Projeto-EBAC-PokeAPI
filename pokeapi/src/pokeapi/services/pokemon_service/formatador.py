"""
Padroniza o formato dos dados de um pokémon em um único lugar.

Antes existiam PELO MENOS três formatos diferentes circulando entre
banco de dados, cache e resposta da API:
  - {'name','id','height','weight','types','sprites': {...}}   (rota GET /pokemons/{id})
  - {'pokemon_name','pokemon_type', ..., 'id': ...}             (rota POST /cadastrar-pokemon)
  - dict parcial só com os campos alterados                     (rota PUT /alterar-pokemon)

Isso fazia o mesmo pokémon ter "cara" diferente dependendo de qual
endpoint o devolveu. Agora todo mundo usa o schema canônico com prefixo
`pokemon_` (o mesmo usado pelas colunas do banco e pelo PokemonResponse).
"""
from typing import Any, Dict


def formatar_pokemon_da_pokeapi(response_json: Dict[str, Any]) -> Dict[str, Any]:
    """Converte o JSON cru da PokeAPI para o schema canônico do projeto."""
    return {
        'pokemon_id': response_json['id'],
        'pokemon_name': response_json['forms'][0]['name'],
        'pokemon_height': response_json['height'],
        'pokemon_weight': response_json['weight'],
        'pokemon_type': [i['type']['name'] for i in response_json['types']],
        'pokemon_sprites': {
            'front_default': response_json['sprites']['front_default'],
            'back_default': response_json['sprites']['back_default'],
        },
    }


def pokemon_orm_para_dict(pokemon) -> Dict[str, Any]:
    """Converte uma instância do modelo CadastroPokemon para o schema canônico."""
    return {
        'pokemon_id': pokemon.pokemon_id,
        'pokemon_name': pokemon.pokemon_name,
        'pokemon_height': pokemon.pokemon_height,
        'pokemon_weight': pokemon.pokemon_weight,
        'pokemon_type': pokemon.pokemon_type,
        'pokemon_sprites': pokemon.pokemon_sprites,
    }
