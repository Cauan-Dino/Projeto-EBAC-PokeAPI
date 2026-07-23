from pokeapi.services.database.criacao_database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

class CadastroPokemon(Base):
    __tablename__ = 'pokemon'
    
    pokemon_id: Mapped[int] = mapped_column(primary_key=True)
    pokemon_name: Mapped[str] = mapped_column(unique=True)
    pokemon_height: Mapped[int] = mapped_column()
    pokemon_weight: Mapped[int] = mapped_column()
    
    pokemon_type: Mapped[list] = mapped_column(JSON)
    pokemon_sprites: Mapped[dict] = mapped_column(JSON)


# Exclui logicamente o pokemon
class ExclusaoPokemon(Base):
    __tablename__ = 'exclusao_pokemon'

    pokemon_id: Mapped[int] = mapped_column(primary_key=True)
    pokemon_nome: Mapped[str] = mapped_column(unique=True)
