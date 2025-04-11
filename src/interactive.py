import readline
import time
from typing import List, Dict, Optional

from src.client import AnthropicClient
from src.command_completer import CommandCompleter
from src.conversation import ConversationManager
from src.streamer import ResponseStreamer
from src.ui import UI


class InteractiveMode:
    """Gestion du mode interactif"""

    def __init__(self, ui: UI, conv_manager: ConversationManager, client: AnthropicClient,
                 streamer: ResponseStreamer):
        """Initialise le mode interactif"""
        self.ui = ui
        self.conv_manager = conv_manager
        self.client = client
        self.streamer = streamer

    async def start(self, args, history: List[Dict], conversation_id: Optional[str] = None):
        """Démarre le mode interactif"""
        # Si aucun ID de conversation n'est fourni, en générer un nouveau
        if not conversation_id:
            conversation_id = time.strftime("%Y%m%d%H%M%S")
            self.ui.print_info(f"Nouvelle conversation créée avec l'ID: {conversation_id}")
        else:
            self.ui.print_info(f"Conversation en cours avec l'ID: {conversation_id}")

        # Afficher l'historique existant
        if history:
            self.ui.display_conversation_history(history)

        # Boucle interactive
        try:
            while True:
                # Obtenir l'entrée de l'utilisateur
                user_input = self.ui.get_input("\n[bold cyan]Vous:[/bold cyan] ")

                # Traiter les commandes spéciales
                if user_input.lower() in ['/exit', '/quit', '/q']:
                    break
                elif user_input.lower() in ['/help', '/?']:
                    self.ui.show_interactive_help()
                    continue
                elif user_input.lower() == '/history':
                    self.ui.display_conversation_history(history)
                    continue
                elif user_input.lower().startswith('/save '):
                    new_id = user_input[6:].strip()
                    if new_id:
                        self.conv_manager.save_conversation_history(new_id, history)
                        conversation_id = new_id
                        self.ui.print_info(f"Conversation sauvegardée avec l'ID: {conversation_id}")
                    else:
                        self.ui.print_error("Veuillez spécifier un ID valide.")
                    continue
                elif user_input.lower() == '/clear':
                    history = []
                    self.ui.print_info("Historique de conversation effacé.")
                    continue
                elif user_input.lower() == '/list':
                    conversations = self.conv_manager.list_conversations()
                    self.ui.show_conversations_list(conversations)
                    continue
                elif user_input.lower().startswith('/load '):
                    load_id = user_input[6:].strip()
                    if load_id:
                        new_history = self.conv_manager.load_conversation_history(load_id)
                        if new_history:
                            history = new_history
                            conversation_id = load_id
                            self.ui.print_info(f"Conversation {load_id} chargée.")
                            self.ui.display_conversation_history(history)
                        else:
                            self.ui.print_error(f"Conversation {load_id} introuvable ou vide.")
                    else:
                        self.ui.print_error("Veuillez spécifier un ID valide.")
                    continue
                elif not user_input.strip():
                    continue

                # Ajouter le message de l'utilisateur à l'historique
                history.append({"role": "user", "content": user_input})

                # Obtenir et afficher la réponse
                try:
                    if args.stream:
                        response_text = await self.streamer.stream_assistant_response(
                            self.client.get_client(), args.model, history, args.max_tokens, args.temperature, args.raw
                        )
                    else:
                        with self.ui.create_progress() as progress:
                            task = progress.add_task("thinking", total=None)
                            response_text = await self.client.send_message(
                                args.model, history, args.max_tokens, args.temperature
                            )

                    # Ajouter la réponse à l'historique
                    history.append({"role": "assistant", "content": response_text})

                    # Afficher la réponse si non streaming
                    if not args.stream:
                        self.ui.print_assistant_response(response_text, args.raw)

                    # Sauvegarder l'historique
                    self.conv_manager.save_conversation_history(conversation_id, history)

                except Exception as e:
                    self.ui.print_error(f"Erreur: {str(e)}")

        except KeyboardInterrupt:
            self.ui.print_info("\nMode interactif terminé.")

        # Sauvegarder l'historique final
        self.conv_manager.save_conversation_history(conversation_id, history)
        self.ui.print_info(f"Conversation sauvegardée avec l'ID: {conversation_id}")

        return history, conversation_id

    def setup_autocompletion(self):
        """Configure l'autocomplétion pour le mode interactif"""
        completer = CommandCompleter(self.conv_manager)
        readline.set_completer(completer.complete)
        readline.parse_and_bind('tab: complete')
        # Sur macOS, vous pourriez avoir besoin de:
        # readline.parse_and_bind('bind ^I rl_complete')
