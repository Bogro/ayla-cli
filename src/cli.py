import argparse
import os
import signal
import sys
import textwrap

from anthropic import (
    Anthropic
)
from rich.console import Console
from rich.panel import Panel

from src.core.handler.analyze_patterns import AnalyzePatterns
from src.core.handler.analyze_project import AnalyzeProjectHandler
from src.core.handler.analyze_project_patterns import AnalyzeProjectPatterns
from src.core.handler.code_analyzer import CodeAnalyzerHandler
from src.core.handler.documentation_generator import DocumentationGeneratorHandler
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
        # Gérer le CTRL+C
        self.running = None
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Commandes disponibles pour le TUI
        self.available_commands = {
            "/help": "Affiche l'aide générale",
            "/quit": "Quitte le mode TUI",
            "/clear": "Efface l'historique de l'écran",
            "/analyze": "Analyse un fichier de code",
            "/document": "Génère de la documentation",
            "/project": "Analyse un projet entier",
            "/list": "Liste les conversations",
            "/save": "Sauvegarde la conversation",
            "/load": "Charge une conversation",
            "/search": "Recherche dans les conversations",
            "/models": "Liste les modèles disponibles",
            "/version": "Affiche la version",
            "/setup": "Configure l'outil",
            "/git-status": "Affiche le statut Git",
            "/git-commit": "Génère un message de commit",
            "/git-branch": "Suggère un nom de branche",
            "/git-analyze": "Analyse le dépôt Git",
            "/git-diff": "Analyse les changements",
            "/git-conventional": "Génère un commit conventionnel",
            "/git-log": "Affiche l'historique Git",
            "/git-visualize": "Visualise l'historique",
            "/git-conflict": "Aide pour les conflits",
            "/git-retrospective": "Génère une rétrospective",
            "/crew": "Commandes de l'équipe AI"
        }

        # Vérifier si le module d'analyse de code est disponible
        try:
            from src.core.modules.code_analysis import (
                CodeAnalyzer, DocumentationGenerator, 
                ProjectAnalyzer, PatternAnalyzer
            )
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
        self.console = Console()
        self.client = Anthropic()
        self.crew_manager = CrewManager(model=self.config.DEFAULT_MODEL)

        # Initialiser le gestionnaire d'analyse de code si disponible
        if self.code_analysis_available:
            os.makedirs(self.config.DEFAULT_ANALYSIS_DIR, exist_ok=True)
            self.code_analyzer = None  # Sera initialisé après l'obtention de la clé API
            self.pattern_analyzer = None  # Sera initialisé après l'obtention de la clé API

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
            description="Ayla CLI - Interface en ligne de commande pour une intéraction avec une IA",
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
              ayla --analyze moncode.py    # Analyser un fichier de code
              ayla --document moncode.py   # Générer de la documentation
              ayla --project ./monprojet   # Analyser un projet entier
              ayla --patterns-analyze moncode.py    # Analyser les design patterns dans un fichier
              ayla --project-patterns ./monprojet   # Analyser les design patterns d'un projet
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
        api_group.add_argument("--timeout", type=int, default=120,
                               help=f"Délai d'attente pour les requêtes API en secondes (défaut: 120)")

        # Options d'entrée/sortie
        io_group = parser.add_argument_group('Options d\'entrée/sortie')
        io_group.add_argument("--file", "-f", action='append', help="Chemin vers un fichier à inclure dans la requête")
        io_group.add_argument("--stream", "-s", action="store_true", help="Afficher la réponse en streaming")
        io_group.add_argument("--raw", "-r", action="store_true", help="Afficher la réponse brute sans formatage")
        io_group.add_argument("--debug", "-d", action="store_true", help="Mode débogage pour le streaming")
        io_group.add_argument("--output", "-o", help="Chemin vers un fichier pour sauvegarder la réponse")
        io_group.add_argument("--auto-save", action="store_true", help="Sauvegarder automatiquement les réponses")

        # Options de conversation
        conv_group = parser.add_argument_group('Options de conversation')
        conv_group.add_argument("--interactive", "-i", action="store_true", help="Mode interactif")
        conv_group.add_argument("--conversation-id", "-c", help="ID de conversation pour sauvegarder l'historique")
        conv_group.add_argument("--continue", dest="continue_conversation", action="store_true",
                                help="Continuer la dernière conversation")

        # ui_group = parser.add_argument_group('Options d\'interface')
        # ui_group.add_argument("--tui", action="store_true",
        #                       help="Lancer en mode TUI (Text User Interface) avec curseur")

        # Options pour l'analyse de code (si le module est disponible)
        if self.code_analysis_available:
            code_group = parser.add_argument_group('Analyse de code')
            code_group.add_argument("--analyze", metavar="FILE", help="Analyser un fichier de code")
            code_group.add_argument("--analysis-type", choices=['general', 'security', 'performance', 'style'],
                                    default='general', help="Type d'analyse de code")
            code_group.add_argument("--document", metavar="FILE",
                                    help="Générer de la documentation pour un fichier de code")
            code_group.add_argument("--doc-type", choices=['complete', 'api', 'usage'],
                                    default='complete', help="Type de documentation")
            code_group.add_argument("--doc-format", choices=['markdown', 'html', 'rst'],
                                    default='markdown', help="Format de la documentation")
            code_group.add_argument("--project", metavar="DIR", help="Analyser un projet entier")
            code_group.add_argument("--extensions", help="Extensions de fichiers à inclure (ex: .py,.js)")
            code_group.add_argument("--exclude-dirs",
                                    help="Répertoires à exclure de l'analyse (séparés par des virgules)")
            code_group.add_argument("--exclude-files",
                                    help="Fichiers à exclure de l'analyse (séparés par des virgules)")
            code_group.add_argument("--no-default-excludes", action="store_true",
                                    help="Ne pas utiliser les exclusions par défaut")
            code_group.add_argument("--output-dir",
                                    help="Dossier où sauvegarder les analyses (défaut: ~/ayla_analyses)")

            # Options pour l'analyse de patterns
            pattern_group = parser.add_argument_group('Analyse de patterns')
            pattern_group.add_argument("--patterns-analyze", metavar="FILE",
                                       help="Analyser les design patterns dans un fichier de code")
            pattern_group.add_argument("--project-patterns", metavar="DIR",
                                       help="Analyser les design patterns dans un projet entier")
            pattern_group.add_argument("--pattern-output",
                                       help="Fichier où sauvegarder l'analyse des patterns")

        # Commandes utilitaires
        util_group = parser.add_argument_group('Commandes utilitaires')
        util_group.add_argument("--list", "-l", action="store_true", help="Lister les conversations sauvegardées")
        util_group.add_argument("--setup", action="store_true", help="Configurer l'outil")
        util_group.add_argument("--models", action="store_true", help="Afficher les modèles disponibles")
        util_group.add_argument("--version", "-v", action="store_true", help="Afficher la version de l'outil")

        # Options Git
        git_group = parser.add_argument_group('Options Git')
        git_group.add_argument("--git-commit", action="store_true",
                               help="Génère un message de commit intelligent pour les changements actuels")
        git_group.add_argument("--git-branch",
                               help="Suggère un nom de branche intelligent basé sur la description fournie")
        git_group.add_argument("--git-analyze", action="store_true",
                               help="Analyse le dépôt Git et fournit des insights")
        git_group.add_argument("--git-diff-analyze", action="store_true",
                               help="Analyse détaillée des changements actuels")
        git_group.add_argument("--git-create-branch", action="store_true",
                               help="Crée une nouvelle branche avec un nom intelligent")
        git_group.add_argument("--git-commit-and-push", action="store_true",
                               help="Commit les changements avec un message intelligent et pousse vers le remote")
        git_group.add_argument("--git-conventional-commit", action="store_true",
                               help="Génère un message de commit au format Conventional Commits")
        git_group.add_argument("--git-stash", action="store", nargs="?", const="", metavar="NOM",
                               help="Crée un stash des modifications courantes avec un nom optionnel")
        git_group.add_argument("--git-stash-apply", action="store_true",
                               help="Applique le dernier stash créé")
        git_group.add_argument("--git-merge", action="store", metavar="BRANCHE",
                               help="Fusionne la branche spécifiée dans la branche courante")
        git_group.add_argument("--git-merge-squash", action="store", metavar="BRANCHE",
                               help="Fusionne la branche spécifiée en un seul commit")
        git_group.add_argument("--git-log", action="store_true",
                               help="Affiche un historique Git amélioré")
        git_group.add_argument("--git-log-format", choices=["default", "detailed", "summary", "stats", "full"],
                               default="default", help="Format d'affichage pour git-log")
        git_group.add_argument("--git-log-count", type=int, default=10,
                               help="Nombre de commits à afficher dans le log")
        git_group.add_argument("--git-log-graph", action="store_true",
                               help="Affiche le log avec un graphe des branches")
        git_group.add_argument("--git-visualize", action="store_true",
                               help="Affiche une visualisation avancée de l'historique Git")
        git_group.add_argument("--git-conflict-assist", action="store_true",
                               help="Fournit une assistance pour résoudre les conflits de fusion")
        git_group.add_argument("--git-retrospective", action="store", type=int, nargs="?",
                               const=14, metavar="JOURS",
                               help="Génère une rétrospective basée sur l'activité récente (14 jours par défaut)")

        return parser

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

        # Initialiser le gestionnaire d'analyse de code si disponible
        if self.code_analysis_available:
            self.code_analyzer = CodeAnalyzer(self.ui.console)
            self.pattern_analyzer = PatternAnalyzer(self.ui.console)

        # Continuer la dernière conversation si demandée
        if args.continue_conversation:
            last_id = self.conv_manager.get_latest_conversation_id()
            if last_id:
                args.conversation_id = last_id
                self.ui.print_info(f"Continuation de la conversation {last_id}")
            else:
                self.ui.print_warning("Aucune conversation précédente trouvée.")

        # Traiter les commandes Git en priorité
        # if await self._process_git_commands(args, api_key):
        #     return

        # Choisir l'action en fonction des arguments
        # if args.tui:
        #     # Lancer l'interface TUI
        #     tui = TUIManager(self)
        #     await tui.start(args, api_key)

        elif args.analyze:
            # Analyser un fichier de code
            analyze = CodeAnalyzerHandler(self.client,
                                           self.ui,
                                           self.crew_manager,
                                           api_key)
            await  analyze.process(args)

        elif args.document:
            # Générer de la documentation
            generate = DocumentationGeneratorHandler(self.client,
                                                     self.ui,
                                                     self.crew_manager,
                                                     api_key,
                                                     self.code_analysis_available,
                                                     self.config)
            await generate.process(args)

        elif args.project:
            # Analyser un projet entier
            analyze_project = AnalyzeProjectHandler(self.client,
                                                    self.ui,
                                                    self.crew_manager,
                                                    api_key)
            await analyze_project.process(args)
            
        elif args.patterns_analyze:
            # Analyser les design patterns dans un fichier
            analyze_patterns = AnalyzePatterns(self.client,
                                               self.ui,
                                               self.crew_manager,
                                               api_key,
                                               self.code_analysis_available,
                                               self.pattern_analyzer)
            await analyze_patterns.process(args)
            
        elif args.project_patterns:
            # Analyser les design patterns dans un projet
            analyze_project_patterns = AnalyzeProjectPatterns(self.client,
                                                               self.ui,
                                                               self.crew_manager,
                                                               api_key,
                                                               self.code_analysis_available,
                                                               self.pattern_analyzer)
            await analyze_project_patterns.process(args)

        else:
            # Traiter une requête standard
            process_request = ProcessRequest(self.client,
                                             self.ui,
                                             self.file_manager,
                                             self.conv_manager,
                                             self.streamer)
            await process_request.process_request(args, api_key)

    def execute_tui_command(self, command: str, parser_args=None, api_key=None):
        """Exécute une commande depuis le TUI et renvoie le résultat"""
        import asyncio
        import traceback

        # Séparer la commande et les arguments
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        cmd_args = parts[1] if len(parts) > 1 else ""

        # Commandes CrewAI
        if cmd.startswith("/crew"):
            crew_args = command.split()[1:]  # Enlève '/crew' du début
            self.crew_manager.init_llm(api_key)
            asyncio.create_task(self.handle_crew_command(command, crew_args))
            return

        try:
            # Commandes d'aide et de navigation
            if cmd == "/help":
                return self._format_help_text()
            elif cmd == "/quit":
                self.running = False
                return "Au revoir !"
            elif cmd == "/clear":
                return "\033[2J\033[H"

            # Commandes de gestion des conversations
            elif cmd == "/list":
                conversations = self.conv_manager.list_conversations()
                return self.ui.format_conversations_list(conversations)
            elif cmd == "/save":
                conv_id = cmd_args if cmd_args else None
                return self.conv_manager.save_conversation(conv_id)
            elif cmd == "/load":
                if not cmd_args:
                    return "Erreur: ID de conversation requis"
                return self.conv_manager.load_conversation(cmd_args)
            elif cmd == "/search":
                if not cmd_args:
                    return "Erreur: Terme de recherche requis"
                return self.conv_manager.search_conversations(cmd_args)

            # Commandes d'analyse de code
            elif cmd == "/analyze":
                if not cmd_args:
                    return "Erreur: Chemin du fichier requis"
                args = parser_args or argparse.Namespace()
                args.analyze = cmd_args
                analyze = CodeAnalyzerHandler(self.client, self.ui, self.crew_manager, api_key)
                asyncio.create_task(analyze.process(args))
                return
            elif cmd == "/document":
                if not cmd_args:
                    return "Erreur: Chemin du fichier requis"
                args = parser_args or argparse.Namespace()
                args.document = cmd_args
                generate = DocumentationGeneratorHandler(self.client,
                                                         self.ui,
                                                         self.crew_manager,
                                                         api_key,
                                                         self.code_analysis_available,
                                                         self.config)
                asyncio.create_task(generate.process(args))
                return
            elif cmd == "/project":
                if not cmd_args:
                    return "Erreur: Chemin du projet requis"
                args = parser_args or argparse.Namespace()
                args.project = cmd_args
                analyze_project = AnalyzeProjectHandler(self.client,
                                                        self.ui,
                                                        self.crew_manager,
                                                        api_key)
                asyncio.create_task(analyze_project.process(args))
                return

            # Commandes Git
            elif cmd.startswith("/git-"):
                return self._handle_git_command(cmd[5:], cmd_args, api_key)

            # Commandes système
            elif cmd == "/models":
                return self.ui.format_models_info(self.config.AVAILABLE_MODELS)
            elif cmd == "/version":
                version = self.config.get('version', 'BETA-1.0.0')
                return f"Ayla CLI v-{version}"
            elif cmd == "/setup":
                setup = AylaSetupAssistant(self.config, self.ui)
                asyncio.create_task(setup.setup())
                return

            # Commande inconnue
            else:
                return (
                    f"Commande inconnue: {cmd}. "
                    "Tapez /help pour voir la liste des commandes."
                )

        except Exception as e:
            error = f"Erreur lors de l'exécution de la commande: {str(e)}"
            if parser_args and hasattr(parser_args, 'debug') and parser_args.debug:
                error += f"\n{traceback.format_exc()}"
            return error

    def _format_help_text(self):
        """Formate le texte d'aide pour le TUI"""
        help_text = [
            "\n=== GUIDE D'UTILISATION DU MODE TUI ===\n",
            "[Navigation et raccourcis]",
            "  Flèches G/D    : Déplacer le curseur",
            "  Flèches H/B    : Historique",
            "  Tab           : Autocomplétation",
            "  Ctrl+H        : Afficher/Masquer aide",
            "  Début/Fin     : Début/fin de ligne",
            "  Suppr         : Supprimer caractère",
            "  Ctrl+C        : Quitter\n",
            "[Commandes principales]"
        ]

        # Ajouter les commandes triées
        for cmd, desc in sorted(self.available_commands.items()):
            help_text.append(f"  {cmd:<12} : {desc}")

        help_text.extend([
            "\n[Interactions]",
            "  1. Questions directes",
            "  2. / pour les commandes",
            "  3. /quit pour quitter"
        ])

        return "\n".join(help_text)

    def _handle_git_command(self, git_cmd: str, args: str, api_key: str):
        """Gère les commandes Git"""
        import asyncio

        if git_cmd == "status":
            return self.git_manager.get_status()
        elif git_cmd == "commit":
            return asyncio.create_task(
                self.git_manager.generate_commit_message(api_key)
            )
        elif git_cmd == "branch":
            if not args:
                return "Erreur: Description de la branche requise"
            return asyncio.create_task(
                self.git_manager.suggest_branch_name(args, api_key)
            )
        elif git_cmd == "analyze":
            return asyncio.create_task(
                self.git_manager.analyze_repository(api_key)
            )
        elif git_cmd == "diff":
            return self.git_manager.analyze_changes()
        elif git_cmd == "conventional":
            return asyncio.create_task(
                self.git_manager.generate_conventional_commit(api_key)
            )
        elif git_cmd == "log":
            return self.git_manager.get_enhanced_log(args)
        elif git_cmd == "visualize":
            return self.git_manager.visualize_history()
        elif git_cmd == "conflict":
            return asyncio.create_task(
                self.git_manager.assist_conflict_resolution(api_key)
            )
        elif git_cmd == "retrospective":
            days = int(args) if args.isdigit() else 7
            return asyncio.create_task(
                self.git_manager.generate_retrospective(days, api_key)
            )
        else:
            return f"Commande Git inconnue: {git_cmd}"

    async def handle_crew_command(self, command: str, args: list):
        """Gère les commandes liées à CrewAI."""
        if command == "/crew research":
            if not args:
                self.console.print("[red]Erreur: Veuillez spécifier un sujet de recherche[/red]")
                return
            topic = " ".join(args)
            crew = self.crew_manager.create_research_crew(topic)
            result = await crew.run()
            self.console.print(result)

        elif command == "/crew review":
            if not args:
                self.console.print("[red]Erreur: Veuillez fournir le code à analyser[/red]")
                return
            code = " ".join(args)
            crew = self.crew_manager.create_code_review_crew(code)
            result = await crew.run()
            self.console.print(result)

    def print_crew_help(self):
        """Affiche l'aide pour les commandes CrewAI."""
        self.console.print(Panel("""
[bold]Commandes CrewAI disponibles:[/bold]

/crew research <sujet>  - Lance une recherche approfondie sur un sujet
/crew review <code>     - Effectue une revue de code complète
        """, title="Aide CrewAI"))