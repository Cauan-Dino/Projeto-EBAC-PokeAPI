

def chave_pokemon(pokemon_id: int) -> str:
    """Chave de cache de um pokémon específico."""
    return f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/'


def chave_paginacao(offset: int, limit: int) -> str:
    """Chave de cache de uma página da listagem de pokémons."""
    return f'https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}'
