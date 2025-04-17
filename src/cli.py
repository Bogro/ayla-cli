import argparse
import os
import signal
import sys

from anthropic import (
    Anthropic
)
from rich.console import Console

from src.core.handler.analyze_patterns import AnalyzePatterns
from src.core.handler.analyze_project import AnalyzeProjectHandler
from src.core.handler.analyze_project_patterns import AnalyzeProjectPatterns
from src.core.handler.code_analyzer import CodeAnalyzerHandler
from src.core.handler.documentation_generator import DocumentationGeneratorHandler
from src.core.handler.process_git_handler import ProcessGitHandler
from src.services.client import AnthropicClient
from src.core.modules.code_analysis import CodeAnalyzer, PatternAnalyzer
from src.config.config import AylaConfig
from src.core.modules.conversation import ConversationManager
from src.core.modules.file_manager import FileManager
from src.core.modules.git_manager import GitManager
from src.core.setup import AylaSetupAssistant
from src.core.streamer import ResponseStreamer
from src.services.process_request import ProcessRequest
from src.core.ui import UI
from src.core.modules.crew_manager import CrewManager


class AylaCli:
    """Classe principale de l'application"""

    def __init__(self):
        """Initialise l'application"""
        # Capturer CTRL+C
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Vérifier si l'analyse de code est disponible
        try:
            import tree_sitter
            self.code_analysis_available = True
        except ImportError:
            self.code_analysis_available = False

        # Initialiser les composants
        self.ui = UI()
        self.config = AylaConfig()
        self.conv_manager = ConversationManager(self.config, self.ui)
        self.file_manager = FileManager(self.ui)
        self.streamer = ResponseStreamer(self.ui)
        self.git_manager = GitManager(self.ui)
        
        # Initialiser le dépôt Git avec le répertoire courant
        self.git_manager.set_repo_path(os.getcwd())
        
        self.console = Console()
        self.client = Anthropic()
        self.crew_manager = CrewManager(
            model=self.config.DEFAULT_MODEL
        )

        # Initialiser le gestionnaire d'analyse de code si disponible
        if self.code_analysis_available:
            os.makedirs(
                self.config.DEFAULT_ANALYSIS_DIR,
                exist_ok=True
            )
            # Sera initialisé après l'obtention de la clé API
            self.code_analyzer = None
            self.pattern_analyzer = None

        # Client sera initialisé plus tard avec la clé API
        self.client = None

        # Créer le parseur d'arguments
        self.parser = AylaSetupAssistant.setup_argparse(self.config)

    def _handle_sigint(self, signal, frame):
        """Gère l'interruption par CTRL+C"""
        self.ui.print_warning("\nOpération annulée par l'utilisateur.")
        sys.exit(0)

    def _get_api_key(self, args) -> str:
        """Obtient la clé API et l'enregistre si nécessaire"""
        api_key = self.config.get_api_key(args)

        if not api_key:
            api_key, save = self.ui.get_api_key_input()
            if save:
                self.config.set("api_key", api_key)
                self.ui.print_info("Clé API sauvegardée dans la configuration.")

        return api_key

    async def send_question_to_claude(self, question):
        """Envoie une question à Claude et retourne la réponse."""
        try:
            history = [{"role": "user", "content": question}]
            response = await self.client.send_message(
                self.config.DEFAULT_MODEL,
                history,
                self.config.DEFAULT_MAX_TOKENS,
                self.config.DEFAULT_TEMPERATURE
            )
            return response
        except Exception as e:
            return f"Erreur lors de l'envoi de la question: {str(e)}"

    async def run(self):
        """Point d'entrée principal de l'application"""
        args = self.parser.parse_args()

        # Afficher la version et quitter
        if args.version:
            self.ui.print_info(f"Ayla CLI v-{self.config.get('version', 'BETA-1.0.0')}")
            return

        # Démarrer le mode setup
        if args.setup:
            setup = AylaSetupAssistant(self.config, self.ui)
            await setup.setup()
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

        # Récupérer la clé API
        api_key = self._get_api_key(args)
        if not api_key:
            return

        # Initialiser le client avec la clé API
        self.client = AnthropicClient(api_key)

        # Continuer la dernière conversation si demandée
        if args.continue_conversation:
            last_id = self.conv_manager.get_latest_conversation_id()
            if last_id:
                args.conversation_id = last_id
                self.ui.print_info(f"Continuation de la conversation {last_id}")
            else:
                self.ui.print_warning("Aucune conversation précédente trouvée.")

        git_commands = [
            'git_commit', 'git_branch', 'git_analyze', 'git_diff_analyze',
            'git_conventional_commit', 'git_create_branch', 'git_commit_and_push',
            'git_stash', 'git_stash_apply', 'git_merge', 'git_merge_squash',
            'git_log', 'git_visualize', 'git_conflict_assist', 'git_retrospective'
        ]

        has_git_command = any(hasattr(args, cmd) and getattr(args, cmd) for cmd in git_commands)
        if has_git_command:
            process_git = ProcessGitHandler(self.client,
                                          self.ui,
                                          self.crew_manager,
                                          api_key,
                                          self.config,
                                          self.git_manager)
            await process_git.process(args)
            return

        # Vérifier si les fonctionnalités d'analyse sont disponibles
        if not self.code_analysis_available:
            if hasattr(args, 'analyze') or hasattr(args, 'document') or \
               hasattr(args, 'project') or hasattr(args, 'patterns_analyze') or \
               hasattr(args, 'project_patterns'):
                self.ui.print_error(
                    "Les fonctionnalités d'analyse de code ne sont pas disponibles. "
                    "Veuillez installer tree-sitter pour utiliser ces fonctionnalités."
                )
                return
        else:
            self.code_analyzer = CodeAnalyzer(self.ui.console)
            self.pattern_analyzer = PatternAnalyzer(self.ui.console)

        # Choisir l'action en fonction des arguments
        if hasattr(args, 'analyze') and args.analyze:
            # Analyser un fichier de code
            analyze = CodeAnalyzerHandler(self.client,
                                          self.ui,
                                          self.crew_manager,
                                          api_key,
                                          self.config)
            await analyze.process(args)

        elif hasattr(args, 'document') and args.document:
            # Générer de la documentation
            generate = DocumentationGeneratorHandler(
                self.client,
                self.ui,
                self.crew_manager,
                api_key,
                self.code_analysis_available,
                self.config
            )
            await generate.process(args)

        elif hasattr(args, 'project') and args.project:
            # Analyser un projet entier
            analyze_project = AnalyzeProjectHandler(
                self.client,
                self.ui,
                self.crew_manager,
                api_key
            )
            await analyze_project.process(args)

        elif hasattr(args, 'patterns_analyze') and args.patterns_analyze:
            # Analyser les design patterns dans un fichier
            analyze_patterns = AnalyzePatterns(
                self.client,
                self.ui,
                self.crew_manager,
                api_key,
                self.code_analysis_available,
                self.pattern_analyzer
            )
            await analyze_patterns.process(args)

        elif hasattr(args, 'project_patterns') and args.project_patterns:
            # Analyser les design patterns dans un projet
            analyze_project_patterns = AnalyzeProjectPatterns(
                self.client,
                self.ui,
                self.crew_manager,
                api_key,
                self.code_analysis_available,
                self.pattern_analyzer
            )
            await analyze_project_patterns.process(args)

        else:
            # Traiter une requête standard
            process_request = ProcessRequest(
                self.client,
                self.ui,
                self.file_manager,
                self.conv_manager,
                self.streamer
            )
            await process_request.process_request(args, api_key)
