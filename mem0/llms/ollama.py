from typing import Dict, List, Optional

try:
    from ollama import Client, ResponseError, RequestError
except ImportError:
    # This part should remain if ollama is not installed,
    # but the task implies ollama is a core dependency here.
    # The original code raises ImportError directly.
    raise ImportError("The 'ollama' library is required. Please install it using 'pip install ollama'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class OllamaLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "llama3.1:70b"
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

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": response["message"]["content"],
                "tool_calls": [],
            }

            if response["message"].get("tool_calls"):
                for tool_call in response["message"]["tool_calls"]:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"],
                        }
                    )

            return processed_response
        else:
            return response["message"]["content"]

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using OpenAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
                "top_p": self.config.top_p,
            },
        }
        if response_format:
            params["format"] = "json"

        if tools:
            params["tools"] = tools

        response = self.client.chat(**params)
        return self._parse_response(response, tools)
