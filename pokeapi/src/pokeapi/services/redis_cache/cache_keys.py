"""
Centraliza a construção das chaves de cache do Redis.

Antes, cada endpoint montava a própria string de chave manualmente
(algumas com barra final, outras sem), o que fazia o SET de um endpoint
não bater com o GET/DELETE de outro (ex.: o endpoint de deletar usava
uma chave sem "/" no final, então o cache nunca era realmente limpo).
Usar estas funções em todo o projeto garante que a mesma chave lógica
sempre gere a mesma string.
"""


def chave_pokemon(pokemon_id: int) -> str:
    """Chave de cache de um pokémon específico."""
    return f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/'


def chave_paginacao(offset: int, limit: int) -> str:
    """Chave de cache de uma página da listagem de pokémons."""
    return f'https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}'
