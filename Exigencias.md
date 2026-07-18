# 🚀 Descritivo Técnico - Projeto de API Pokémon com Python

## 🎯 Objetivo
Construir uma API RESTful em Python que consuma dados da **[PokeAPI](https://pokeapi.co/)** e os disponibilize de forma paginada. A API deverá estar dockerizada, testada, com CI/CD configurado, e publicada em um serviço de deploy.

---

## ✅ Requisitos Técnicos

### ### 1. Linguagem e Framework
- Utilizar **Python 3.10+**
- Framework sugerido: **FastAPI**

### ### 2. Consumo de Dados
- A API deve **consumir dados da PokeAPI** (https://pokeapi.co/api/v2/pokemon/)
- Armazenamento local (opcional): Pode fazer cache local para performance, mas o consumo deve ser da PokeAPI originalmente

### ### 3. Endpoints Mínimos
- `GET /pokemons`: lista de pokémons paginada
- `GET /pokemons/{id}`: detalhes de um pokémon específico

### ### 4. Paginação
- O endpoint `/pokemons` deve aceitar:
  - `?limit=20&offset=0` (ou `?page=1&size=20`, a definir)
- A resposta deve incluir:
```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "next": "/pokemons?limit=20&offset=20",
    "previous": null
  }
}
```

### ### 5. Formato do JSON de Resposta
- Para o endpoint `/pokemons`:
```json
{
  "name": "pikachu",
  "id": 25,
  "height": 4,
  "weight": 60,
  "types": ["electric"],
  "sprites": {
    "front_default": "https://raw.githubusercontent.com/...",
    "back_default": "https://raw.githubusercontent.com/..."
  }
}
```
- Os dados devem ser extraídos diretamente da PokeAPI

### ### 6. Docker
- Criar um `Dockerfile` funcional
- Criar `docker-compose.yml` se houver necessidade de serviços adicionais (ex: cache, banco)

### ### 7. Testes Unitários
- Escrever testes com **pytest**
- Cobrir pelo menos:
  - Resposta dos endpoints
  - Paginação
  - Erros (ex: Pokémon não encontrado)
- Gerar relatório de cobertura com `pytest-cov`

### ### 8. CI/CD
- Configurar workflow de CI/CD com **GitHub Actions**
- Etapas mínimas do CI:
  - Instalação de dependências
  - Execução dos testes
  - Verificação de cobertura
  - Lint (opcional)
- Etapas do CD:
  - Deploy automático após `push` na branch principal

### ### 9. Deploy
- Publicar a API em um serviço gratuito como:
  - [Render](https://render.com/)
  - [Railway](https://railway.app/)
  - [Vercel com Python](https://vercel.com/)
  - Heroku (se ainda tiver acesso)
- O endereço final da API deve estar acessível publicamente

### ### 10. Integração CI/CD com Deploy
- O deploy deve acontecer automaticamente via pipeline configurada no GitHub Actions

### ### 11. Organização do Projeto
- Recomendado seguir estrutura modular:
```text
├── app/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   ├── models/
│   └── utils/
├── tests/
├── Dockerfile
├── requirements.txt
└── .github/workflows/
```
- Usar **tipagem com type hints** em todas as funções

### ### 12. Documentação
- Utilizar a documentação automática do **FastAPI (Swagger UI)**
- Incluir um `README.md` com:
  - Descrição do projeto
  - Como rodar localmente
  - Como executar testes
  - Link de produção (API em produção)
  - Exemplo de requisição e resposta da API

---

## 🔍 Extras (Desejáveis, mas não obrigatórios)
- **Cache com Redis** para performance (opcional)
- **Tratamento de exceções personalizado**
- **Rate limiting ou autenticação simples (ex: via API Key)**
- **Logs estruturados**
- **Uso de `pydantic` para validação de dados**