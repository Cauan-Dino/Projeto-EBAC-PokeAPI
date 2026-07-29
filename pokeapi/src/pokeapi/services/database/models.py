from pokeapi.services.database.criacao_database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON


class CadastroPokemon(Base):
    """
    Tabela única de pokémons cadastrados.

    A exclusão é lógica (soft delete) através da coluna `pokemon_excluido`.
    Antes existia uma tabela separada (`exclusao_pokemon`) apenas duplicando
    `pokemon_id`/nome, sem nenhuma relação real (FK) com esta tabela — o que
    permitia inconsistência entre as duas (um pokémon podia existir em uma e
    não na outra). Unificar em uma única tabela com uma flag resolve isso:
    uma única fonte de verdade por pokémon.
    """
    __tablename__ = 'pokemon'

    pokemon_id: Mapped[int] = mapped_column(primary_key=True)
    pokemon_name: Mapped[str] = mapped_column(unique=True, index=True)
    pokemon_height: Mapped[int] = mapped_column()
    pokemon_weight: Mapped[int] = mapped_column()

    pokemon_type: Mapped[list] = mapped_column(JSON)
    pokemon_sprites: Mapped[dict] = mapped_column(JSON)

    # Soft delete: substitui a antiga tabela ExclusaoPokemon
    pokemon_excluido: Mapped[bool] = mapped_column(default=False, server_default='0', index=True)
