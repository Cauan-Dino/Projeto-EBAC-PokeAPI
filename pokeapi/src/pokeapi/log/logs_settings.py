import logging.config
import yaml
from elasticsearch import AsyncElasticsearch
import os
from datetime import datetime

ES_HOST = os.getenv('ES_HOST', 'localhost')
ES_PORT = os.getenv('ES_PORT', '9200')

# Conecta com o elasticsearch
es_client = AsyncElasticsearch(hosts=[f'http://{ES_HOST}:{ES_PORT}'])

# Pega o caminho absoluto onde logs_settings.py esta armazenado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Junta o caminho absoluto com o logging.yaml
YAML = os.path.join(BASE_DIR, 'logging.yaml')


with open(YAML,'r') as f: # Lê o arquivo logging.yaml
    config = yaml.safe_load(f) # Transforma o conteúdo no logging.yaml em dict
    log_path = os.getenv('LOG_FILE_PATH', os.path.join(BASE_DIR, 'logs', 'app.log'))
    config['handlers']['file']['filename'] = log_path

    os.makedirs(os.path.dirname(log_path), exist_ok=True) # Garante que a pasta exista 

    logging.config.dictConfig(config)

logger = logging.getLogger(__name__) # Defini o nome dos logs. Nesse caso os nomes serão os nomes dos arquivos 


# Função pra registrar log e enviar pro elasticsearch
async def registrar_log_de_buscar_pokemon(
    credencias: str | None, 
    offset: int | None, 
    limit: int | None, 
    origem: str, 
    endpoint: str, 
    status: str
    ):
    # Log que vai ser enviado pro elasticsearch
    log = {
        'timestamp': datetime.utcnow().isoformat(),
        'endpoint': endpoint,
        'usuario': credencias,
        'page': offset,
        'limit': limit,
        'origem': origem, # Cache, requisição http etc
        'status': status
    } 

    try:
        await es_client.index(index='pokeapi-logs',body=log) # Envia o log pro elasticsearch em background
    except Exception as e:
        logger.error(f'Erro ao enviar log para o Elasticsearch: {e}')
