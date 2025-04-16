import time
import random
import logging

from anthropic import (
    Anthropic, 
    RateLimitError, 
    APIConnectionError, 
    APIStatusError, 
    APIError
)

from src.services.cache import ResponseCache


class AnthropicClient:
    """Client pour l'API Anthropic"""

    def __init__(self, api_key: str, max_retries=3, base_delay=1.0, logger=None):
        """Initialise le client avec la clé API
        
        Args:
            api_key: Clé API Anthropic
            max_retries: Nombre maximum de tentatives en cas d'erreur temporaire
            base_delay: Délai de base entre les tentatives (en secondes)
            logger: Logger pour enregistrer les événements
        """
        self.cache = ResponseCache('./cache')
        self.client = self._create_client(api_key)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logger or logging.getLogger(__name__)

    def _create_client(self, api_key: str):
        """Crée un client Anthropic avec la clé API"""
        return Anthropic(api_key=api_key)

    async def send_message(self, model, messages, max_tokens, temperature, use_cache=True):
        """Envoie un message à l'API et retourne la réponse, avec cache optionnel et retry"""
        last_user_message = None

        if use_cache:
            # Extraire le dernier message utilisateur pour le cache
            last_user_message = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), 
                None
            )
            if last_user_message:
                cached_response = self.cache.get(model, last_user_message, temperature)
                if cached_response:
                    return cached_response

        # Tentatives avec backoff exponentiel
        retry_count = 0
        last_exception = None

        while retry_count <= self.max_retries:
            try:
                # Procéder avec l'appel API normal
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

            except RateLimitError as e:
                last_exception = e
                retry_count += 1
                if retry_count <= self.max_retries:
                    # Backoff exponentiel avec jitter
                    delay = (self.base_delay * (2 ** (retry_count - 1)) + 
                             random.uniform(0, 0.5))
                    self.logger.warning(
                        f"Limite de taux dépassée. Nouvelle tentative dans {delay:.2f} secondes..."
                    )
                    time.sleep(delay)
                else:
                    raise
            except APIConnectionError as e:
                last_exception = e
                retry_count += 1
                if retry_count <= self.max_retries:
                    # Backoff exponentiel avec jitter
                    delay = (self.base_delay * (2 ** (retry_count - 1)) + 
                             random.uniform(0, 0.5))
                    self.logger.warning(
                        f"Erreur de connexion. Nouvelle tentative dans {delay:.2f} secondes..."
                    )
                    time.sleep(delay)
                else:
                    raise
            except (APIStatusError, APIError) as e:
                # Les erreurs de statut ou les erreurs d'API générales ne sont généralement pas temporaires
                # Nous les propageons directement
                raise
            except Exception as e:
                # Pour les autres exceptions inattendues, on les propage également
                self.logger.error(f"Erreur inattendue: {str(e)}")
                raise

        # Si nous arrivons ici, c'est que toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        raise Exception("Échec de l'envoi du message après plusieurs tentatives")

    def get_client(self):
        """Récupère le client Anthropic"""
        return self.client
