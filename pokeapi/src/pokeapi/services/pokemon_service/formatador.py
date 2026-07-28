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
