from typing import List, Dict

from src.views.ui import UI


class ResponseStreamer:
    """Gestion du streaming des réponses"""

    def __init__(self, ui: UI):
        """Initialise le streamer de réponses"""
        self.ui = ui

    async def stream_assistant_response(self, client, model: str, messages: List[Dict],
                                        max_tokens: int, temperature: float, raw: bool = False) -> str:
        """Stream la réponse de l'assistant en temps réel"""
        try:
            with self.ui.create_progress() as progress:
                progress.add_task("thinking", total=None)
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                    stream=True
                )

                # Effacer la barre de progression
                progress.stop()

            # Préparation pour l'affichage
            if not raw:
                self.ui.console.print("\n[assistant]Ayla:[/assistant]")

            full_response = ""

            # Pour la bibliothèque Anthropic moderne (v0.5.0+)
            for chunk in response:
                # Extraire le texte selon le type d'événement
                text = None

                # L'API peut renvoyer différents types d'événements
                if hasattr(chunk, 'type'):
                    # Messages API v1 (format le plus récent)
                    if chunk.type == 'content_block_delta':
                        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                            text = chunk.delta.text
                    elif chunk.type == 'content_block_start' or chunk.type == 'content_block_stop':
                        # Ignorer les événements de début/fin de bloc
                        pass
                elif hasattr(chunk, 'completion') and chunk.completion:
                    # Ancien format de l'API Completions
                    text = chunk.completion
                elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    # Autre format possible
                    text = chunk.delta.text
                elif hasattr(chunk, 'content') and chunk.content:
                    # Format alternatif
                    text = chunk.content

                # Afficher le texte si disponible
                if text:
                    if raw:
                        print(text, end="", flush=True)
                    else:
                        self.ui.console.print(text, end="")
                    full_response += text

            if not raw:
                self.ui.console.print("\n")
            else:
                print("\n")

            return full_response

        except Exception as e:
            self.ui.print_error(f"Erreur lors du streaming: {str(e)}")
            return "Erreur de streaming"

    async def stream_assistant_response_debug(self, client, model: str, messages: List[Dict],
                                              max_tokens: int, temperature: float, raw: bool = False) -> str:
        """Version de debug du streaming pour comprendre la structure des événements"""
        try:
            self.ui.print_info("Mode débogage activé pour le streaming")

            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                stream=True
            )

            # Examiner quelques événements pour comprendre leur structure
            first_events = []
            counter = 0
            full_response = ""

            for i, chunk in enumerate(response):
                if i < 3:  # Examiner seulement les 3 premiers événements
                    first_events.append(chunk)
                    self.ui.print_info(f"Événement {i + 1}:")
                    self.ui.console.print(self._print_event_structure(chunk))

                # Essayer différentes façons d'accéder au texte
                text = None

                # Méthode 1: Vérifier s'il s'agit d'un événement de contenu
                if hasattr(chunk, 'content') and chunk.content:
                    text = chunk.content
                    counter += 1
                # Méthode 2: Vérifier le delta.text si disponible
                elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text') and chunk.delta.text:
                    text = chunk.delta.text
                    counter += 1
                # Méthode 3: Vérifier le type d'événement (pour les versions récentes de l'API)
                elif hasattr(chunk, 'type'):
                    self.ui.console.print(f"[info]Type d'événement trouvé: {chunk.type}[/info]", end="")
                    if chunk.type == 'content_block_start':
                        self.ui.console.print(" (Début du bloc de contenu)")
                    elif chunk.type == 'content_block_delta':
                        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                            text = chunk.delta.text
                            counter += 1
                    elif chunk.type == 'content_block_stop':
                        self.ui.console.print(" (Fin du bloc de contenu)")
                    elif chunk.type == 'message_start':
                        self.ui.console.print(" (Début du message)")
                    elif chunk.type == 'message_stop':
                        self.ui.console.print(" (Fin du message)")

                if text:
                    full_response += text
                    if not raw:
                        self.ui.console.print(text, end="")
                    else:
                        print(text, end="", flush=True)

            if not raw:
                self.ui.console.print("\n")
            else:
                print("\n")

            self.ui.print_info(f"Nombre total d'événements avec du texte: {counter}")

            return full_response

        except Exception as e:
            self.ui.print_error(f"Erreur lors du débogage du streaming: {str(e)}")
            import traceback
            self.ui.console.print(traceback.format_exc())
            return "Erreur de streaming (debug)"

    def _print_event_structure(self, event, indent=0):
        """Affiche la structure d'un événement pour le débogage"""
        if isinstance(event, (str, int, float, bool, type(None))):
            return str(event)

        result = ""
        if hasattr(event, "__dict__"):
            for key, value in event.__dict__.items():
                if key.startswith("_"):  # Ignorer les attributs privés
                    continue
                result += f"\n{'  ' * indent}{key}: {self._print_event_structure(value, indent + 1)}"
        elif isinstance(event, dict):
            for key, value in event.items():
                result += f"\n{'  ' * indent}{key}: {self._print_event_structure(value, indent + 1)}"
        elif isinstance(event, (list, tuple)):
            for i, item in enumerate(event):
                result += f"\n{'  ' * indent}{i}: {self._print_event_structure(item, indent + 1)}"
        else:
            result = str(type(event))

        return result
