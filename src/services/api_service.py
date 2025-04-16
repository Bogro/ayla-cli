from anthropic import APIError, APIConnectionError, APIStatusError, RateLimitError
from src.services.client import AnthropicClient

class APIService:
    def __init__(self, ui):
        self.ui = ui
        self.client = None

    def initialize_client(self, api_key):
        self.client = AnthropicClient(api_key)
        return self.client

    async def send_message(self, model, history, max_tokens, temperature):
        try:
            return await self.client.send_message(model, history, max_tokens, temperature)
        except RateLimitError:
            self.ui.print_error(
                "Limite de taux dépassée. Veuillez réessayer plus tard ou :\n"
                "1. Réduire la fréquence de vos requêtes\n"
                "2. Utiliser un token de plus petite taille (--max-tokens)\n"
                "3. Utiliser un modèle plus léger (--model claude-3-5-haiku-20240307)"
            )
        except APIStatusError as e:
            self._handle_status_error(e)
        except APIConnectionError:
            self._handle_connection_error()
        except APIError as e:
            self._handle_api_error(e)
        return None

    def _handle_status_error(self, e):
        status_code = getattr(e, "status_code", "inconnu")
        self.ui.print_error(
            f"Erreur API (statut {status_code}): {str(e)}\n"
            f"Suggestions :\n"
            f"- Si code 401/403 : Vérifiez votre clé API\n"
            f"- Si code 404 : Vérifiez le nom du modèle\n"
            f"- Si code 429 : Réduisez la fréquence des requêtes\n"
            f"- Si code 500+ : Problème côté serveur, réessayez plus tard"
        )

    def _handle_connection_error(self):
        self.ui.print_error(
            "Erreur de connexion à l'API. Vérifiez :\n"
            "1. Votre connexion Internet\n"
            "2. La disponibilité du service Anthropic\n"
            "3. Les paramètres de proxy/firewall"
        )

    def _handle_api_error(self, e):
        error_code = getattr(e, "error_code", "")
        message = str(e)
        specific_advice = self._get_specific_advice(message)
        
        error_message = f"Erreur API générale: {message}"
        if error_code:
            error_message += f" (Code: {error_code})"
        if specific_advice:
            error_message += f"\n→ {specific_advice}"
            
        self.ui.print_error(error_message)

    def _get_specific_advice(self, message):
        if "insufficient_quota" in message.lower() or "quota" in message.lower():
            return "Votre quota API est probablement épuisé. Vérifiez votre facturation."
        elif "invalid_api_key" in message.lower():
            return "Votre clé API semble invalide. Utilisez '--setup' pour la reconfigurer."
        elif "model" in message.lower() and "not found" in message.lower():
            return "Le modèle spécifié n'existe pas. Utilisez '--models' pour voir les modèles disponibles."
        return "" 