import os
import json

USER_ID = os.getenv("USER", "default_user")
DEFAULT_APP_ID = "openmemory"

def load_config():
    # Path to default_config.json, assuming execution from repo root /app
    config_path = 'openmemory/api/default_config.json'

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # Fallback or error handling if default_config.json is not found
        # For now, let's raise an error or return a minimal default
        raise FileNotFoundError(f"Configuration file {config_path} not found. Please ensure it exists.")
    except json.JSONDecodeError:
        # Handle cases where the JSON is malformed
        raise ValueError(f"Error decoding JSON from {config_path}. Please check its format.")

    # Override with environment variables if set
    llm_provider_env = os.getenv('MEM0_LLM_PROVIDER')
    if llm_provider_env:
        config['mem0']['llm']['provider'] = llm_provider_env

    llm_model_env = os.getenv('MEM0_LLM_MODEL')
    if llm_model_env:
        # Ensure 'config' key exists
        if 'config' not in config['mem0']['llm']:
            config['mem0']['llm']['config'] = {}
        config['mem0']['llm']['config']['model'] = llm_model_env

    ollama_base_url_env = os.getenv('MEM0_OLLAMA_BASE_URL')
    if ollama_base_url_env:
        if config['mem0']['llm']['provider'] == 'ollama':
            # Ensure 'config' key exists
            if 'config' not in config['mem0']['llm']:
                config['mem0']['llm']['config'] = {}
            config['mem0']['llm']['config']['ollama_base_url'] = ollama_base_url_env
        if config['mem0']['embedder']['provider'] == 'ollama':
            # Ensure 'config' key exists
            if 'config' not in config['mem0']['embedder']:
                config['mem0']['embedder']['config'] = {}
            config['mem0']['embedder']['config']['ollama_base_url'] = ollama_base_url_env

    embedder_provider_env = os.getenv('MEM0_EMBEDDER_PROVIDER')
    if embedder_provider_env:
        config['mem0']['embedder']['provider'] = embedder_provider_env

    embedder_model_env = os.getenv('MEM0_EMBEDDER_MODEL')
    if embedder_model_env:
        # Ensure 'config' key exists
        if 'config' not in config['mem0']['embedder']:
            config['mem0']['embedder']['config'] = {}
        config['mem0']['embedder']['config']['model'] = embedder_model_env

    return config

CONFIG = load_config()