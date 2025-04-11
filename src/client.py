from typing import List, Dict

from anthropic import Anthropic

from src.cache import ResponseCache


class AnthropicClient:
    """Client pour l'API Anthropic"""

    def __init__(self, api_key: str):
        """Initialise le client avec la clé API"""
        self.cache = ResponseCache('./cache')
        self.client = self._create_client(api_key)

    def _create_client(self, api_key: str):
        """Crée un client Anthropic avec la clé API"""
        return Anthropic(api_key=api_key)

    async def send_message(self, model, messages, max_tokens, temperature, use_cache=True):
        """Envoie un message à l'API et retourne la réponse, avec cache optionnel"""
        last_user_message = None

        if use_cache:
            # Extraire le dernier message utilisateur pour le cache
            last_user_message = next((m["content"] for m in reversed(messages)
                                      if m["role"] == "user"), None)
            if last_user_message:
                cached_response = self.cache.get(model, last_user_message, temperature)
                if cached_response:
                    return cached_response

        # Procéder avec l'appel API normal si pas de cache
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages
        )
        response_text = response.content[0].text

        # Mettre en cache la réponse
        if use_cache and last_user_message:
            self.cache.set(model, last_user_message, temperature, response_text)

        return response_text

    def get_client(self):
        """Récupère le client Anthropic"""
        return self.client
