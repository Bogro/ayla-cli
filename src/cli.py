import argparse
import signal
import sys
import textwrap

from anthropic import APIError, APIConnectionError, APIStatusError, RateLimitError

from src.client import AnthropicClient
from src.config import AylaConfig
from src.conversation import ConversationManager
from src.file_manager import FileManager
from src.interactive import InteractiveMode
from src.setup import AylaSetupAssistant
from src.streamer import ResponseStreamer
from src.ui import UI


class AylaCli:
    """Classe principale de l'application"""

    def __init__(self):
        """Initialise l'application"""
        # Gérer le CTRL+C
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Initialiser les composants
        self.ui = UI()
        self.config = AylaConfig()
        self.conv_manager = ConversationManager(self.config, self.ui)
        self.file_manager = FileManager(self.ui)
        self.streamer = ResponseStreamer(self.ui)

        # Client sera initialisé plus tard avec la clé API
        self.client = None

        # Créer le parseur d'arguments
        self.parser = self._setup_argparse()

    def _handle_sigint(self, signal, frame):
        """Gère l'interruption par CTRL+C"""
        self.ui.print_warning("\nOpération annulée par l'utilisateur.")
        sys.exit(0)

    def _setup_argparse(self):
        """Configure le parseur d'arguments"""
        parser = argparse.ArgumentParser(
            description="Ayla CLI - Interface en ligne de commande pour Claude",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
            Exemples d'utilisation:
              ayla "Quelle est la capitale de la France?"
              ayla -f moncode.py "Explique ce code"
              cat fichier.txt | ayla "Résume ce texte"
              ayla -i                      # Mode interactif
              ayla -c abc123               # Continuer une conversation existante
              ayla --list                  # Lister les conversations
              ayla --setup                 # Configurer l'outil
            """)
        )

        # Arguments principaux
        parser.add_argument("prompt", nargs="*", help="Votre question ou demande pour Ayla")

        # Options du modèle et de l'API
        api_group = parser.add_argument_group('Options API')
        api_group.add_argument("--api-key",
                               help="Clé API Anthropic (sinon utilise ANTHROPIC_API_KEY ou la configuration)")
        api_group.add_argument("--model", "-m", default=self.config.DEFAULT_MODEL,
                               help=f"Modèle Ayla à utiliser (défaut: {self.config.DEFAULT_MODEL})")
        api_group.add_argument("--max-tokens", "-t", type=int, default=self.config.DEFAULT_MAX_TOKENS,
                               help=f"Nombre maximum de tokens pour la réponse (défaut: {self.config.DEFAULT_MAX_TOKENS})")
        api_group.add_argument("--temperature", "-T", type=float, default=self.config.DEFAULT_TEMPERATURE,
                               help=f"Température pour la génération (0.0-1.0, défaut: {self.config.DEFAULT_TEMPERATURE})")

        # Options d'entrée/sortie
        io_group = parser.add_argument_group('Options d\'entrée/sortie')
        io_group.add_argument("--file", "-f", action='append', help="Chemin vers un fichier à inclure dans la requête")
        io_group.add_argument("--stream", "-s", action="store_true", help="Afficher la réponse en streaming")
        io_group.add_argument("--raw", "-r", action="store_true", help="Afficher la réponse brute sans formatage")
        io_group.add_argument("--debug", "-d", action="store_true", help="Mode débogage pour le streaming")

        # Options de conversation
        conv_group = parser.add_argument_group('Options de conversation')
        conv_group.add_argument("--interactive", "-i", action="store_true", help="Mode interactif")
        conv_group.add_argument("--conversation-id", "-c", help="ID de conversation pour sauvegarder l'historique")
        conv_group.add_argument("--continue", dest="continue_conversation", action="store_true",
                                help="Continuer la dernière conversation")

        # Commandes utilitaires
        util_group = parser.add_argument_group('Commandes utilitaires')
        util_group.add_argument("--list", "-l", action="store_true", help="Lister les conversations sauvegardées")
        util_group.add_argument("--setup", action="store_true", help="Configurer l'outil")
        util_group.add_argument("--models", action="store_true", help="Afficher les modèles disponibles")
        util_group.add_argument("--version", "-v", action="store_true", help="Afficher la version de l'outil")

        return parser

    def _get_api_key(self, args):
        """Obtient la clé API et l'enregistre si nécessaire"""
        api_key = self.config.get_api_key(args)

        if not api_key:
            api_key, save = self.ui.get_api_key_input()
            if save:
                self.config.set("api_key", api_key)
                self.ui.print_info("Clé API sauvegardée dans la configuration.")

        return api_key

    async def _process_request(self, args, api_key):
        """Traite une requête à Ayla"""
        if not self.client:
            self.client = AnthropicClient(api_key)

        # Initialiser les classes dépendantes
        interactive_mode = InteractiveMode(self.ui, self.conv_manager, self.client, self.streamer)

        # Construire le message utilisateur
        prompt_text = " ".join(args.prompt)

        # Lire depuis l'entrée standard si nécessaire
        if not prompt_text and not sys.stdin.isatty():
            prompt_text = sys.stdin.read().strip()

        # Ajouter le contenu des fichiers si spécifiés
        if args.file:
            file_contents = []
            for file_path in args.file:
                content = self.file_manager.read_file_content(file_path)
                if content:
                    file_contents.append(f"Contenu du fichier {file_path}:\n\n{content}")

            if file_contents:
                if prompt_text:
                    prompt_text += "\n\n" + "\n\n".join(file_contents)
                else:
                    prompt_text = "\n\n".join(file_contents)

        # Vérifier si nous avons un message à envoyer
        if not prompt_text and not args.interactive and not args.continue_conversation:
            if args.conversation_id:
                # Si un ID de conversation est spécifié mais pas de prompt, afficher l'historique
                history = self.conv_manager.load_conversation_history(args.conversation_id)
                self.ui.display_conversation_history(history)
                return
            else:
                # Sinon, entrer en mode interactif
                args.interactive = True

        # Charger l'historique de conversation si nécessaire
        history = []
        if args.conversation_id:
            history = self.conv_manager.load_conversation_history(args.conversation_id)

        # Si on continue une conversation mais sans prompt, utiliser le mode interactif
        if args.continue_conversation and not prompt_text:
            args.interactive = True

        # Mode interactif
        if args.interactive:
            await interactive_mode.start(args, history, args.conversation_id)
            return

        # Ajouter le nouveau message à l'historique
        if prompt_text:
            history.append({"role": "user", "content": prompt_text})

        # Afficher le message utilisateur
        if not args.raw:
            self.ui.print_user(prompt_text)

        # Envoyer la requête et obtenir la réponse
        try:
            if args.stream:
                # Mode de débogage si demandé
                if args.debug:
                    response_text = await self.streamer.stream_assistant_response_debug(
                        self.client.get_client(), args.model, history, args.max_tokens, args.temperature, args.raw
                    )
                else:
                    response_text = await self.streamer.stream_assistant_response(
                        self.client.get_client(), args.model, history, args.max_tokens, args.temperature, args.raw
                    )
            else:
                with self.ui.create_progress(transient=not args.raw) as progress:
                    task = progress.add_task("thinking", total=None)
                    response_text = await self.client.send_message(
                        args.model, history, args.max_tokens, args.temperature
                    )

            # Ajouter la réponse à l'historique
            history.append({"role": "assistant", "content": response_text})

            # Afficher la réponse
            if not args.stream:
                self.ui.print_assistant_response(response_text, args.raw)

            # Sauvegarder l'historique si un ID de conversation est spécifié
            if args.conversation_id:
                self.conv_manager.save_conversation_history(args.conversation_id, history)

            return response_text

        except RateLimitError:
            self.ui.print_error("Limite de taux dépassée. Veuillez réessayer plus tard.")
        except APIStatusError as e:
            self.ui.print_error(f"Erreur API: {str(e)}")
        except APIConnectionError:
            self.ui.print_error("Erreur de connexion à l'API. Vérifiez votre connexion Internet.")
        except APIError as e:
            self.ui.print_error(f"Erreur API générale: {str(e)}")
        except Exception as e:
            self.ui.print_error(f"Erreur inattendue: {str(e)}")
            import traceback
            self.ui.console.print(traceback.format_exc())

    async def run(self):
        """Fonction principale de l'application"""
        # Analyser les arguments
        args = self.parser.parse_args()

        # Afficher la version
        if args.version:
            self.ui.console.print("[bold]Ayla CLI[/bold] v1.0.0")
            return

        # Afficher les modèles disponibles
        if args.models:
            self.ui.show_models_info(self.config.AVAILABLE_MODELS)
            return

        # Lister les conversations
        if args.list:
            conversations = self.conv_manager.list_conversations()
            self.ui.show_conversations_list(conversations)
            return

        # Mode configuration
        if args.setup:
            setup_assistant = AylaSetupAssistant(self.config, self.ui)
            await setup_assistant.setup()
            return

        # Charger la dernière conversation si demandé
        if args.continue_conversation and not args.conversation_id:
            conversation_id = self.conv_manager.get_latest_conversation_id()
            if conversation_id:
                args.conversation_id = conversation_id
                self.ui.print_info(f"Continuation de la conversation la plus récente: {args.conversation_id}")
            else:
                self.ui.print_warning(
                    "Aucune conversation existante trouvée. Démarrage d'une nouvelle conversation.")

        # Obtenir la clé API
        api_key = self._get_api_key(args)

        # Traiter la requête
        await self._process_request(args, api_key)