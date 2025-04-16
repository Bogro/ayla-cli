import argparse
import os
import signal
import sys
import textwrap
from typing import Dict, Any

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
        # Capturer CTRL+C
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Vérifier si l'analyse de code est disponible
        self.code_analysis_available = True
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
        self.parser = self._setup_argparse()

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

    def _handle_sigint(self, signal, frame):
        """Gère l'interruption par CTRL+C"""
        self.ui.print_warning("\nOpération annulée par l'utilisateur.")
        sys.exit(0)

    def _setup_argparse(self):
        """Configure le parseur d'arguments"""
        desc = "Ayla CLI - Interface en ligne de commande pour une IA"
        parser = argparse.ArgumentParser(
            description=desc,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
            Exemples d'utilisation:
              ayla "Quelle est la capitale de la France?"
              ayla -f moncode.py "Explique ce code"
              cat fichier.txt | ayla "Résume ce texte"
              ayla -i                      # Mode interactif
              ayla -c abc123               # Continuer une conversation
              ayla --list                  # Lister les conversations
              ayla --setup                 # Configurer l'outil
            """)
        )

        # Arguments principaux
        parser.add_argument("prompt", nargs="*", help="Question ou demande")

        # Options du modèle et de l'API
        api_group = parser.add_argument_group('Options API')
        api_group.add_argument(
            "--api-key",
            help="Clé API Anthropic"
        )
        api_group.add_argument(
            "--model", "-m",
            default=self.config.DEFAULT_MODEL,
            help="Modèle à utiliser"
        )
        api_group.add_argument(
            "--max-tokens", "-t",
            type=int,
            default=self.config.DEFAULT_MAX_TOKENS,
            help="Nombre maximum de tokens"
        )
        api_group.add_argument(
            "--temperature", "-T",
            type=float,
            default=self.config.DEFAULT_TEMPERATURE,
            help="Température (0.0-1.0)"
        )
        api_group.add_argument(
            "--timeout",
            type=int,
            default=120,
            help="Délai d'attente en secondes"
        )

        # Options d'entrée/sortie
        io_group = parser.add_argument_group('Options E/S')
        io_group.add_argument(
            "--file", "-f",
            action='append',
            help="Fichier à inclure"
        )
        io_group.add_argument(
            "--stream", "-s",
            action="store_true",
            help="Afficher en streaming"
        )
        io_group.add_argument(
            "--raw", "-r",
            action="store_true",
            help="Sortie brute"
        )
        io_group.add_argument(
            "--debug", "-d",
            action="store_true",
            help="Mode débogage"
        )
        io_group.add_argument(
            "--output", "-o",
            help="Fichier de sortie"
        )
        io_group.add_argument(
            "--auto-save",
            action="store_true",
            help="Sauvegarde auto"
        )

        # Options de conversation
        conv_group = parser.add_argument_group('Conversation')
        conv_group.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Mode interactif"
        )
        conv_group.add_argument(
            "--conversation-id", "-c",
            help="ID de conversation"
        )
        conv_group.add_argument(
            "--continue",
            dest="continue_conversation",
            action="store_true",
            help="Continuer conversation"
        )

        # Options pour l'analyse de code
        code_group = parser.add_argument_group('Analyse de code')
        code_group.add_argument(
            "--analyze",
            metavar="FILE",
            help="Analyser un fichier"
        )
        code_group.add_argument(
            "--analysis-type",
            choices=['general', 'security', 'performance', 'style'],
            default='general',
            help="Type d'analyse"
        )
        code_group.add_argument(
            "--document",
            metavar="FILE",
            help="Générer documentation"
        )
        code_group.add_argument(
            "--doc-type",
            choices=['complete', 'api', 'usage'],
            default='complete',
            help="Type de doc"
        )
        code_group.add_argument(
            "--doc-format",
            choices=['markdown', 'html', 'rst'],
            default='markdown',
            help="Format de doc"
        )
        code_group.add_argument(
            "--project",
            metavar="DIR",
            help="Analyser projet"
        )
        code_group.add_argument(
            "--extensions",
            help="Extensions (.py,.js)"
        )
        code_group.add_argument(
            "--exclude-dirs",
            help="Répertoires exclus"
        )
        code_group.add_argument(
            "--exclude-files",
            help="Fichiers exclus"
        )
        code_group.add_argument(
            "--no-default-excludes",
            action="store_true",
            help="Sans exclusions"
        )
        code_group.add_argument(
            "--output-dir",
            help="Dossier de sortie"
        )

        # Options pour l'analyse de patterns
        pattern_group = parser.add_argument_group('Patterns')
        pattern_group.add_argument(
            "--patterns-analyze",
            metavar="FILE",
            help="Analyser patterns dans un fichier"
        )
        pattern_group.add_argument(
            "--project-patterns",
            metavar="DIR",
            help="Analyser patterns dans un projet"
        )
        pattern_group.add_argument(
            "--pattern-output",
            help="Fichier de sortie pour l'analyse"
        )

        # Commandes utilitaires
        util_group = parser.add_argument_group('Utilitaires')
        util_group.add_argument(
            "--list", "-l",
            action="store_true",
            help="Lister conversations"
        )
        util_group.add_argument(
            "--setup",
            action="store_true",
            help="Configuration"
        )
        util_group.add_argument(
            "--models",
            action="store_true",
            help="Liste des modèles"
        )
        util_group.add_argument(
            "--version", "-v",
            action="store_true",
            help="Version"
        )

        # Options Git
        git_group = parser.add_argument_group('Git')
        git_group.add_argument(
            "--git-commit",
            action="store_true",
            help="Message de commit"
        )
        git_group.add_argument(
            "--git-branch",
            help="Nom de branche"
        )
        git_group.add_argument(
            "--git-analyze",
            action="store_true",
            help="Analyser dépôt"
        )
        git_group.add_argument(
            "--git-diff-analyze",
            action="store_true",
            help="Analyser diff"
        )
        git_group.add_argument(
            "--git-create-branch",
            action="store_true",
            help="Créer branche"
        )
        git_group.add_argument(
            "--git-commit-and-push",
            action="store_true",
            help="Commit et push"
        )
        git_group.add_argument(
            "--git-conventional-commit",
            action="store_true",
            help="Commit conventionnel"
        )
        git_group.add_argument(
            "--git-stash",
            action="store",
            nargs="?",
            const="",
            metavar="NOM",
            help="Stash"
        )
        git_group.add_argument(
            "--git-stash-apply",
            action="store_true",
            help="Appliquer stash"
        )
        git_group.add_argument(
            "--git-merge",
            action="store",
            metavar="BRANCHE",
            help="Fusionner branche"
        )
        git_group.add_argument(
            "--git-merge-squash",
            action="store",
            metavar="BRANCHE",
            help="Fusionner en squash"
        )
        git_group.add_argument(
            "--git-log",
            action="store_true",
            help="Log amélioré"
        )
        git_group.add_argument(
            "--git-log-format",
            choices=["default", "detailed", "summary", "stats", "full"],
            default="default",
            help="Format du log"
        )
        git_group.add_argument(
            "--git-log-count",
            type=int,
            default=10,
            help="Nombre de commits"
        )
        git_group.add_argument(
            "--git-log-graph",
            action="store_true",
            help="Log avec graphe"
        )
        git_group.add_argument(
            "--git-visualize",
            action="store_true",
            help="Visualisation"
        )
        git_group.add_argument(
            "--git-conflict-assist",
            action="store_true",
            help="Aide conflits"
        )
        git_group.add_argument(
            "--git-retrospective",
            action="store",
            type=int,
            nargs="?",
            const=14,
            metavar="JOURS",
            help="Rétrospective"
        )

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
        if await self._process_git_commands(args, api_key):
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

        # Choisir l'action en fonction des arguments
        if hasattr(args, 'analyze') and args.analyze:
            # Analyser un fichier de code
            analyze = CodeAnalyzerHandler(self.client,
                                        self.ui,
                                        self.crew_manager,
                                        api_key)
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
        elif git_cmd == "diff-analyze":
            # Analyser les changements
            analysis = self.git_manager.analyze_changes()
            
            if "error" in analysis:
                self.ui.print_error(analysis["error"])
                return True
                
            # Afficher le résumé
            self.ui.print_info("\n[bold cyan]=== Résumé des Changements ===[/bold cyan]")
            summary = analysis["summary"]
            self.ui.print_info(Panel(
                f"[white]Fichiers modifiés : [bold]{summary['files_changed']}[/bold]\n"
                f"Lignes ajoutées   : [bold green]+{summary['insertions']}[/bold green]\n"
                f"Lignes supprimées : [bold red]-{summary['deletions']}[/bold red][/white]",
                title="Statistiques",
                border_style="cyan"
            ).renderable)
            
            # Afficher les changements par statut
            self.ui.print_info("\n[bold cyan]=== État des Fichiers ===[/bold cyan]")
            
            # Créer des sections pour chaque type de changement
            staged_content = ""
            if analysis["staged_changes"]:
                staged_content = "\n".join(f"[green]+ {file[0]} ({file[1]})[/green]" 
                                         for file in analysis["staged_changes"])
            
            unstaged_content = ""
            if analysis["unstaged_changes"]:
                unstaged_content = "\n".join(f"[yellow]* {file[0]} ({file[1]})[/yellow]" 
                                           for file in analysis["unstaged_changes"])
            
            untracked_content = ""
            if analysis["untracked_files"]:
                untracked_content = "\n".join(f"[dim]? {file}[/dim]" 
                                            for file in analysis["untracked_files"])
            
            # Afficher les sections dans des panels
            if staged_content:
                self.ui.print_info(Panel(
                    staged_content,
                    title="[green]Fichiers indexés[/green]",
                    border_style="green"
                ).renderable)
            
            if unstaged_content:
                self.ui.print_info(Panel(
                    unstaged_content,
                    title="[yellow]Fichiers modifiés non indexés[/yellow]",
                    border_style="yellow"
                ).renderable)
            
            if untracked_content:
                self.ui.print_info(Panel(
                    untracked_content,
                    title="[dim]Fichiers non suivis[/dim]",
                    border_style="dim"
                ).renderable)
            
            # Afficher les détails par fichier
            self.ui.print_info("\n[bold cyan]=== Détails par Fichier ===[/bold cyan]")
            file_details = []
            for file_path, details in analysis["file_details"].items():
                total_changes = details["added"] + details["deleted"]
                file_details.append(
                    f"[bold]{file_path}[/bold]\n"
                    f"  [green]+ {details['added']}[/green] "
                    f"[red]- {details['deleted']}[/red] "
                    f"([yellow]{total_changes} changements[/yellow])"
                )
            
            if file_details:
                self.ui.print_info(Panel(
                    "\n".join(file_details),
                    title="Modifications par fichier",
                    border_style="cyan"
                ).renderable)
            
            # Afficher l'analyse d'impact
            if analysis["impact_analysis"]:
                self.ui.print_info("\n[bold cyan]=== Analyse d'Impact ===[/bold cyan]")
                
                for file_path, impact in analysis["impact_analysis"].items():
                    # Niveau de risque avec code couleur
                    risk_color = {
                        "low": "green",
                        "medium": "yellow",
                        "high": "red"
                    }.get(impact["risk_level"], "white")
                    
                    impact_content = [
                        f"[bold]{file_path}[/bold]",
                        f"[bold]Niveau de risque :[/bold] [{risk_color}]{impact['risk_level'].upper()}[/{risk_color}]"
                    ]
                    
                    if impact["reasons"]:
                        impact_content.append("\n[bold]Raisons :[/bold]")
                        impact_content.extend(
                            f"  [yellow]• {reason}[/yellow]" 
                            for reason in impact["reasons"]
                        )
                    
                    if impact["suggestions"]:
                        impact_content.append("\n[bold]Suggestions :[/bold]")
                        impact_content.extend(
                            f"  [green]> {suggestion}[/green]" 
                            for suggestion in impact["suggestions"]
                        )
                    
                    self.ui.print_info(Panel(
                        "\n".join(impact_content),
                        border_style="cyan"
                    ).renderable)
            
            return True
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

    async def _process_git_commands(self, args, api_key: str) -> bool:
        """
        Traite toutes les commandes Git disponibles.

        Args :
            args : Arguments de la ligne de commande
            api_key : Clé API pour les fonctionnalités IA

        Returns :
            bool : True si une commande Git a été traitée, False sinon
        """
        # Vérifier si une commande Git est demandée
        git_commands = [
            'git_commit', 'git_branch', 'git_analyze', 'git_diff_analyze',
            'git_conventional_commit', 'git_create_branch', 'git_commit_and_push',
            'git_stash', 'git_stash_apply', 'git_merge', 'git_merge_squash',
            'git_log', 'git_visualize', 'git_conflict_assist', 'git_retrospective'
        ]

        has_git_command = any(hasattr(args, cmd) and getattr(args, cmd) for cmd in git_commands)
        if not has_git_command:
            return False

        # Initialiser le gestionnaire Git si ce n'est pas déjà fait
        if not hasattr(self, 'git_manager'):
            self.git_manager = GitManager(self.ui)
            # Utiliser le répertoire courant comme dépôt
            if not self.git_manager.set_repo_path(os.getcwd()):
                self.ui.print_error("Le répertoire courant n'est pas un dépôt Git valide")
                return True

        # Définir le client pour les appels à l'IA
        self.git_manager.set_client(self.client)

        try:
            # Traiter chaque commande Git
            if args.git_commit:
                # Obtenir le diff actuel
                diff = self.git_manager.get_detailed_diff()
                # Générer un message de commit avec Claude
                message = await self.git_manager.generate_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                # Créer le commit
                self.git_manager.commit_changes(message)

            elif args.git_branch and args.git_branch != True:
                # Suggérer un nom de branche et la créer
                branch_name = await self.git_manager.suggest_branch_name(args.description)
                self.git_manager.switch_branch(branch_name, create=True)

            elif args.git_analyze:
                # Analyser le dépôt
                analysis = await self.git_manager.analyze_repository(api_key)

                # Vérifier s'il y a une erreur
                if "error" in analysis:
                    self.ui.print_error(analysis["error"])
                    return True

                # Afficher les informations générales
                self.ui.print_info("\n=== Informations Générales ===")
                info = analysis["general_info"]
                self.ui.print_info(f"Branche actuelle : {info['current_branch']}")
                self.ui.print_info(f"Nombre total de commits : {info['total_commits']}")
                self.ui.print_info(f"Taille du dépôt : {info['repository_size']}")
                self.ui.print_info(f"Date de création : {info['creation_date']}")

                # Afficher l'activité
                self.ui.print_info("\n=== Activité ===")
                activity = analysis["activity"]
                self.ui.print_info("Fréquence des commits :")
                for period, count in activity["commit_frequency"].items():
                    self.ui.print_info(f"- {period} : {count} commits")

                # Afficher les branches
                self.ui.print_info("\n=== Branches ===")
                branches = analysis["branches"]
                self.ui.print_info(f"Nombre total de branches : {branches['total_count']}")
                self.ui.print_info(f"Branches actives : {len(branches['active_branches'])}")
                self.ui.print_info(f"Branches fusionnées : {len(branches['merged_branches'])}")

                # Afficher les contributeurs
                self.ui.print_info("\n=== Contributeurs ===")
                contributors = analysis["contributors"]
                self.ui.print_info(f"Nombre total : {contributors['total_count']}")
                if contributors['top_contributors']:
                    self.ui.print_info("Top contributeurs :")
                    for contrib in contributors['top_contributors'][:3]:
                        self.ui.print_info(f"- {contrib['name']} : {contrib['commits']} commits")

                # Afficher la santé du code
                self.ui.print_info("\n=== Santé du Code ===")
                health = analysis["code_health"]
                self.ui.print_info("Qualité des commits :")
                quality = health["commit_quality"]
                self.ui.print_info(f"- Messages descriptifs : {quality['descriptive_messages']}")
                self.ui.print_info(f"- Commits conventionnels : {quality['conventional_commits']}")

                # Afficher les insights IA
                self.ui.print_info("\n=== Insights IA ===")
                for insight in analysis["insights"]:
                    self.ui.print_info(f"- {insight}")

            elif args.git_diff_analyze:
                # Analyser les changements
                analysis = self.git_manager.analyze_changes()
                self._display_git_analysis(analysis)

            elif args.git_conventional_commit:
                # Générer un message de commit conventionnel
                diff = self.git_manager.get_detailed_diff()
                message = await self.git_manager.generate_conventional_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                self.git_manager.commit_changes(message)

            elif args.git_create_branch and args.git_create_branch != True:
                # Créer une nouvelle branche
                self.git_manager.switch_branch(args.git_create_branch, create=True)

            elif args.git_commit_and_push:
                # Commit et push en une seule commande
                diff = self.git_manager.get_detailed_diff()
                message = await self.git_manager.generate_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                if self.git_manager.commit_changes(message):
                    self.git_manager.push_changes()

            elif args.git_stash:
                # Gérer les stash
                self.git_manager.stash_changes(
                    name=args.git_stash if isinstance(args.git_stash, str) else None
                )

            elif args.git_stash_apply:
                # Appliquer le dernier stash
                success, output = self.git_manager._run_git_command(['stash', 'apply'])
                if success:
                    self.ui.print_success("Stash appliqué avec succès")
                else:
                    self.ui.print_error(f"Erreur lors de l'application du stash: {output}")

            elif args.git_merge:
                # Fusionner une branche
                self.git_manager.merge_branch(args.git_merge)

            elif args.git_merge_squash:
                # Fusionner une branche en squash
                self.git_manager.merge_branch(args.git_merge_squash, squash=True)

            elif args.git_log:
                # Afficher le log amélioré
                format_type = getattr(args, 'git_log_format', 'default')
                count = getattr(args, 'git_log_count', 10)
                show_graph = getattr(args, 'git_log_graph', False)
                log = self.git_manager.get_enhanced_log(
                    format_type=format_type,
                    count=count,
                    show_graph=show_graph
                )
                self.ui.print_info(log)

            elif args.git_visualize:
                # Visualiser l'historique
                viz = self.git_manager.visualize_git_history(
                    include_all_branches=True,
                    include_stats=True
                )
                self.ui.print_info(viz)

            elif args.git_conflict_assist:
                # Assister dans la résolution des conflits
                try:
                    conflicts = self.git_manager.assist_merge_conflicts(
                        self.git_manager.current_branch
                    )
                    self.ui.print_info(conflicts)
                except Exception as e:
                    self.ui.print_info(str(e))

            elif args.git_retrospective:
                # Générer une rétrospective
                days = args.git_retrospective if isinstance(args.git_retrospective, int) else 14
                retro = self.git_manager.generate_sprint_retrospective(days=days)
                self.ui.print_info(retro)

            return True

        except Exception as e:
            self.ui.print_error(f"Erreur lors du traitement de la commande Git: {str(e)}")
            return True

    def _display_git_analysis(self, analysis: Dict[str, Any]) -> None:
        """Affiche l'analyse Git de manière formatée"""
        # Afficher les changements par statut
        self.ui.print_info("\n[bold cyan]=== État des Fichiers ===[/bold cyan]")
        
        # Créer des sections pour chaque type de changement
        staged_content = ""
        if analysis["staged_changes"]:
            staged_content = "\n".join(
                f"[green]+ {file[0]} ({file[1]})[/green]" 
                for file in analysis["staged_changes"]
            )
        
        unstaged_content = ""
        if analysis["unstaged_changes"]:
            unstaged_content = "\n".join(
                f"[yellow]* {file[0]} ({file[1]})[/yellow]" 
                for file in analysis["unstaged_changes"]
            )
        
        untracked_content = ""
        if analysis["untracked_files"]:
            untracked_content = "\n".join(
                f"[dim]? {file}[/dim]" 
                for file in analysis["untracked_files"]
            )
        
        # Afficher les sections dans des panels
        if staged_content:
            self.ui.print_info(Panel(
                staged_content,
                title="[green]Fichiers indexés[/green]",
                border_style="green"
            ).renderable)
        
        if unstaged_content:
            self.ui.print_info(Panel(
                unstaged_content,
                title="[yellow]Fichiers modifiés non indexés[/yellow]",
                border_style="yellow"
            ).renderable)
        
        if untracked_content:
            self.ui.print_info(Panel(
                untracked_content,
                title="[dim]Fichiers non suivis[/dim]",
                border_style="dim"
            ).renderable)
        
        # Afficher les détails par fichier
        self.ui.print_info("\n[bold cyan]=== Détails par Fichier ===[/bold cyan]")
        file_details = []
        for file_path, details in analysis["file_details"].items():
            total_changes = details["added"] + details["deleted"]
            file_details.append(
                f"[bold]{file_path}[/bold]\n"
                f"  [green]+ {details['added']}[/green] "
                f"[red]- {details['deleted']}[/red] "
                f"([yellow]{total_changes} changements[/yellow])"
            )
        
        if file_details:
            self.ui.print_info(Panel(
                "\n".join(file_details),
                title="Modifications par fichier",
                border_style="cyan"
            ).renderable)
        
        # Afficher l'analyse d'impact
        if analysis["impact_analysis"]:
            self.ui.print_info("\n[bold cyan]=== Analyse d'Impact ===[/bold cyan]")
            
            for file_path, impact in analysis["impact_analysis"].items():
                # Niveau de risque avec code couleur
                risk_color = {
                    "low": "green",
                    "medium": "yellow",
                    "high": "red"
                }.get(impact["risk_level"], "white")
                
                impact_content = [
                    f"[bold]{file_path}[/bold]",
                    f"[bold]Niveau de risque :[/bold] [{risk_color}]{impact['risk_level'].upper()}[/{risk_color}]"
                ]
                
                if impact["reasons"]:
                    impact_content.append("\n[bold]Raisons :[/bold]")
                    impact_content.extend(
                        f"  [yellow]• {reason}[/yellow]" 
                        for reason in impact["reasons"]
                    )
                
                if impact["suggestions"]:
                    impact_content.append("\n[bold]Suggestions :[/bold]")
                    impact_content.extend(
                        f"  [green]> {suggestion}[/green]" 
                        for suggestion in impact["suggestions"]
                    )
                
                self.ui.print_info(Panel(
                    "\n".join(impact_content),
                    border_style="cyan"
                ).renderable)