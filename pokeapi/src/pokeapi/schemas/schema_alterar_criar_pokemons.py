from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Optional


class InserirInformacoesPokemon(BaseModel):
    pokemon_name: str = Field(..., description="Nome do pokémon", examples=["pikachu"])
    pokemon_type: List[str] = Field(
        ..., description="Lista com os tipos do pokémon", examples=[["electric"]]
    )
    pokemon_height: int = Field(..., description="Altura do pokémon (decímetros)", examples=[4])
    pokemon_weight: int = Field(..., description="Peso do pokémon (hectogramas)", examples=[60])
    pokemon_sprites: Dict[str, Optional[str]] = Field(
        ...,
        description="URLs dos sprites do pokémon",
        examples=[{"front_default": "https://.../25.png", "back_default": "https://.../back/25.png"}],
    )


class AlterarInformacoesPokemon(BaseModel):
    pokemon_name: Optional[str] = Field(None, description="Novo nome do pokémon", examples=["raichu"])
    pokemon_type: Optional[List[str]] = Field(
        None, description="Novos tipos do pokémon", examples=[["electric"]]
    )
    pokemon_height: Optional[int] = Field(None, description="Nova altura do pokémon", examples=[6])
    pokemon_weight: Optional[int] = Field(None, description="Novo peso do pokémon", examples=[90])
    pokemon_sprites: Optional[Dict[str, Optional[str]]] = Field(
        None, description="Novas URLs de sprites do pokémon"
    )


class PokemonResponse(BaseModel):
    """Schema padrão de retorno de um pokémon, usado em todos os endpoints
    que retornam dados de um pokémon (cache, banco de dados ou PokeAPI)."""

    model_config = ConfigDict(from_attributes=True)

    pokemon_id: int = Field(..., description="Identificador único do pokémon", examples=[25])
    pokemon_name: str = Field(..., description="Nome do pokémon", examples=["pikachu"])
    pokemon_height: int = Field(..., description="Altura do pokémon (decímetros)", examples=[4])
    pokemon_weight: int = Field(..., description="Peso do pokémon (hectogramas)", examples=[60])
    pokemon_type: List[str] = Field(..., description="Tipos do pokémon", examples=[["electric"]])
    pokemon_sprites: Dict[str, Optional[str]] = Field(
        ..., description="URLs dos sprites (imagens) do pokémon"
    )


class PaginacaoInfo(BaseModel):
    limit: int = Field(..., examples=[20])
    offset: int = Field(..., examples=[0])
    next: Optional[str] = Field(None, examples=["https://pokeapi.co/api/v2/pokemon/?offset=20&limit=20"])
    previous: Optional[str] = Field(None, examples=[None])
    count: int = Field(..., examples=[1302])


class PokemonPaginadoResponse(BaseModel):
    """Schema de retorno da listagem paginada de pokémons."""

    data: List[Dict] = Field(..., description="Lista de pokémons retornados pela PokeAPI")
    pagination: PaginacaoInfo


class MensagemResponse(BaseModel):
    message: str = Field(..., examples=["Pokémon cadastrado com sucesso!"])


class ErroResponse(BaseModel):
    detail: str = Field(..., examples=["Pokémon com id 9999 não encontrado"])
