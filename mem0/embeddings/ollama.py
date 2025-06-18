import subprocess
import sys
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    from ollama import Client, ResponseError, RequestError
except ImportError:
    user_input = input("The 'ollama' library is required. Install it now? [y/N]: ")
    if user_input.lower() == "y":
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
            from ollama import Client, ResponseError, RequestError
        except subprocess.CalledProcessError:
            print("Failed to install 'ollama'. Please install it manually using 'pip install ollama'.")
            sys.exit(1)
    else:
        print("The required 'ollama' library is not installed.")
        sys.exit(1)


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-embed-text"
        self.config.embedding_dims = self.config.embedding_dims or 512

        self.client = Client(host=self.config.ollama_base_url)
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        try:
            # Attempt to get host from client._host, fallback to config if not found
            host_url = getattr(self.client, '_host', self.config.ollama_base_url)
            local_models = self.client.list()["models"]
        except RequestError as e:
            raise ValueError(
                f"Failed to connect to Ollama server at {host_url}. "
                f"Please ensure Ollama is running and accessible. Original error: {e}"
            )
        except Exception as e: # Catch any other unexpected errors during list
            raise ValueError(
                f"An unexpected error occurred while listing Ollama models: {e}"
            )

        if not any(model.get("name") == self.config.model for model in local_models):
            print(f"Model '{self.config.model}' not found locally. Pulling from Ollama server...")
            try:
                # Attempt to get host from client._host, fallback to config if not found
                host_url = getattr(self.client, '_host', self.config.ollama_base_url)
                self.client.pull(self.config.model)
                print(f"Successfully pulled model '{self.config.model}'.")
            except ResponseError as e:
                if e.status_code == 404: # Or check e.error for "not found" if more reliable
                    raise ValueError(
                        f"Ollama model '{self.config.model}' not found on the server. "
                        f"Please ensure the model name is correct and available."
                    )
                else:
                    raise ValueError(
                        f"Error pulling Ollama model '{self.config.model}' from server. "
                        f"Status: {e.status_code}, Error: {e.error if hasattr(e, 'error') else str(e)}"
                    )
            except RequestError as e:
                raise ValueError(
                    f"Failed to connect to Ollama server at {host_url} "
                    f"while trying to pull model '{self.config.model}'. Original error: {e}"
                )
            except Exception as e: # Catch any other unexpected errors during pull
                raise ValueError(
                    f"An unexpected error occurred while pulling Ollama model '{self.config.model}': {e}"
                )

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        response = self.client.embeddings(model=self.config.model, prompt=text)
        return response["embedding"]
