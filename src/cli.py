import argparse
import os
import signal
import sys
import textwrap
import time

from anthropic import APIError, APIConnectionError, APIStatusError, RateLimitError

from src.client import AnthropicClient
from src.config import AylaConfig
from src.conversation import ConversationManager
from src.file_manager import FileManager
from src.git_manager import GitManager
from src.interactive import InteractiveMode
from src.setup import AylaSetupAssistant
from src.streamer import ResponseStreamer
from src.ui import UI, TUIManager


class AylaCli:
    """Classe principale de l'application"""

    def __init__(self):
        """Initialise l'application"""
        # Gérer le CTRL+C
        signal.signal(signal.SIGINT, self._handle_sigint)

        # Vérifier si le module d'analyse de code est disponible
        try:
            from src.code_analysis import CodeAnalyzer, DocumentationGenerator, ProjectAnalyzer, PatternAnalyzer
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
              ayla --analyze moncode.py    # Analyser un fichier de code
              ayla --document moncode.py   # Générer de la documentation
              ayla --project ./monprojet   # Analyser un projet entier
              ayla --patterns-analyze moncode.py    # Analyser les design patterns dans un fichier
              ayla --project-patterns ./monprojet   # Analyser les design patterns d'un projet
              ayla --tui                   # Lancer l'interface TUI
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

        ui_group = parser.add_argument_group('Options d\'interface')
        ui_group.add_argument("--tui", action="store_true",
                              help="Lancer en mode TUI (Text User Interface) avec curseur")

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

            # Sauvegarder la réponse dans un fichier si demandé
            if hasattr(args, 'output') and args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(response_text)
                self.ui.print_success(f"Réponse sauvegardée dans le fichier: {args.output}")

            return response_text

        except RateLimitError:
            self.ui.print_error(
                "Limite de taux dépassée. Veuillez réessayer plus tard ou :\n"
                "1. Réduire la fréquence de vos requêtes\n"
                "2. Utiliser un token de plus petite taille (--max-tokens)\n"
                "3. Utiliser un modèle plus léger (--model claude-3-5-haiku-20240307)"
            )
        except APIStatusError as e:
            status_code = getattr(e, "status_code", "inconnu")
            self.ui.print_error(
                f"Erreur API (statut {status_code}): {str(e)}\n"
                f"Suggestions :\n"
                f"- Si code 401/403 : Vérifiez votre clé API\n"
                f"- Si code 404 : Vérifiez le nom du modèle\n"
                f"- Si code 429 : Réduisez la fréquence des requêtes\n"
                f"- Si code 500+ : Problème côté serveur, réessayez plus tard"
            )
        except APIConnectionError:
            self.ui.print_error(
                "Erreur de connexion à l'API. Vérifiez :\n"
                "1. Votre connexion Internet\n"
                "2. La disponibilité du service Anthropic\n"
                "3. Les paramètres de proxy/firewall"
            )
        except APIError as e:
            error_code = getattr(e, "error_code", "")
            message = str(e)

            # Essayer d'extraire des informations utiles de l'erreur
            specific_advice = ""
            if "insufficient_quota" in message.lower() or "quota" in message.lower():
                specific_advice = "Votre quota API est probablement épuisé. Vérifiez votre facturation."
            elif "invalid_api_key" in message.lower():
                specific_advice = "Votre clé API semble invalide. Utilisez '--setup' pour la reconfigurer."
            elif "model" in message.lower() and "not found" in message.lower():
                specific_advice = f"Le modèle spécifié n'existe pas. Utilisez '--models' pour voir les modèles disponibles."

            error_message = f"Erreur API générale: {message}"
            if error_code:
                error_message += f" (Code: {error_code})"
            if specific_advice:
                error_message += f"\n→ {specific_advice}"

            self.ui.print_error(error_message)
        except Exception as e:
            self.ui.print_error(f"Erreur inattendue: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())

    async def _analyze_code(self, args, api_key):
        """Analyse un fichier de code avec Ayla"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        file_path = args.analyze
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)

        # Créer l'analyseur de code
        from src.code_analysis import CodeAnalyzer
        analyzer = CodeAnalyzer(self.ui.console)

        try:
            # Charger le fichier
            file_info = analyzer.load_file(file_path)
            self.ui.print_info(f"Analyse du fichier: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Générer le prompt d'analyse
            analysis_type = args.analysis_type
            prompt = analyzer.generate_analysis_prompt(analysis_type)

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task(f"Analyse {analysis_type}", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Afficher la réponse
            self.ui.print_assistant_response(response, args.raw)

            # Déterminer le dossier de sortie
            output_dir = None
            if hasattr(args, 'output_dir') and args.output_dir:
                output_dir = args.output_dir
            elif hasattr(self.config, 'ANALYSIS_DIR'):
                output_dir = self.config.ANALYSIS_DIR

            # Créer le dossier de sortie s'il existe et n'existe pas déjà
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Sauvegarder la réponse
            if hasattr(args, 'output') and args.output:
                # Si output_dir est spécifié et args.output n'est pas un chemin absolu, combiner les deux
                if output_dir and not os.path.isabs(args.output):
                    output_file = os.path.join(output_dir, args.output)
                else:
                    output_file = args.output

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")
            elif hasattr(args, 'auto_save') and args.auto_save:
                base_name = os.path.splitext(os.path.basename(file_path))[0]

                # Si output_dir est spécifié, l'utiliser; sinon, utiliser le répertoire courant
                if output_dir:
                    output_file = os.path.join(output_dir, f"{base_name}_analysis_{analysis_type}.md")
                else:
                    output_file = f"{base_name}_analysis_{analysis_type}.md"

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")

            return response

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse du code: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
            return None

    async def _generate_documentation(self, args, api_key):
        """Génère de la documentation pour un fichier de code avec Ayla"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        file_path = args.document
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)

        # Créer le générateur de documentation
        from code_analysis import DocumentationGenerator
        doc_gen = DocumentationGenerator(self.ui.console)

        try:
            # Charger le fichier
            file_info = doc_gen.load_file(file_path)
            self.ui.print_info(
                f"Génération de documentation pour: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Générer le prompt de documentation
            doc_format = args.doc_format
            doc_type = args.doc_type
            prompt = doc_gen.generate_documentation_prompt(doc_format, doc_type)

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task(f"Génération de documentation ({doc_type})", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Traiter la réponse pour extraire la documentation
            doc_content = doc_gen.process_documentation(response, doc_format)

            # Afficher la réponse
            self.ui.print_assistant_response(doc_content, args.raw)

            # Déterminer le dossier de sortie
            output_dir = None
            if hasattr(args, 'output_dir') and args.output_dir:
                output_dir = args.output_dir
            elif hasattr(self.config, 'ANALYSIS_DIR'):
                output_dir = self.config.ANALYSIS_DIR

            # Créer le dossier de sortie s'il existe et n'existe pas déjà
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Sauvegarder la documentation
            if hasattr(args, 'output') and args.output:
                # Si output_dir est spécifié et args.output n'est pas un chemin absolu, combiner les deux
                if output_dir and not os.path.isabs(args.output):
                    output_file = os.path.join(output_dir, args.output)
                else:
                    output_file = args.output
            else:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                doc_extension = ".txt" if doc_format == 'rst' else f".{doc_format}"

                # Si output_dir est spécifié, l'utiliser; sinon, utiliser le répertoire courant
                if output_dir:
                    output_file = os.path.join(output_dir, f"{base_name}_documentation{doc_extension}")
                else:
                    output_file = f"{base_name}_documentation{doc_extension}"

            # Sauvegarder avec le générateur de documentation
            doc_gen.save_documentation(doc_content, output_file)
            self.ui.print_success(f"Documentation sauvegardée dans le fichier: {output_file}")

            return doc_content

        except Exception as e:
            self.ui.print_error(f"Erreur lors de la génération de documentation: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
            return None

    async def _analyze_project(self, args, api_key):
        """Analyse un projet entier avec Ayla"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        project_dir = args.project
        if not os.path.isdir(project_dir):
            self.ui.print_error(f"Le répertoire {project_dir} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)

        # Configurer les exclusions
        excluded_dirs = []
        excluded_files = []

        # Si on ne veut pas utiliser les exclusions par défaut
        if not args.no_default_excludes:
            from src.code_analysis import ProjectAnalyzer
            excluded_dirs.extend(ProjectAnalyzer.DEFAULT_EXCLUDED_DIRS)
            excluded_files.extend(ProjectAnalyzer.DEFAULT_EXCLUDED_FILES)

        # Ajouter les exclusions spécifiées par l'utilisateur
        if args.exclude_dirs:
            custom_dirs = [d.strip() for d in args.exclude_dirs.split(',')]
            excluded_dirs.extend(custom_dirs)
            self.ui.print_info(f"Répertoires exclus supplémentaires: {', '.join(custom_dirs)}")

        if args.exclude_files:
            custom_files = [f.strip() for f in args.exclude_files.split(',')]
            excluded_files.extend(custom_files)
            self.ui.print_info(f"Fichiers exclus supplémentaires: {', '.join(custom_files)}")

        # Créer l'analyseur de projet avec les exclusions personnalisées
        from src.code_analysis import ProjectAnalyzer
        project_analyzer = ProjectAnalyzer(
            project_dir,
            self.ui.console,
            excluded_dirs=excluded_dirs,
            excluded_files=excluded_files
        )

        try:
            # Traiter les extensions de fichiers si spécifiées
            extensions = None
            if args.extensions:
                extensions = [ext.strip() for ext in args.extensions.split(',')]
                # Ajouter un point au début si nécessaire
                extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
                self.ui.print_info(f"Recherche de fichiers avec extensions: {', '.join(extensions)}")

            # Scanner le projet
            files = project_analyzer.scan_project(extensions)

            if not files:
                self.ui.print_warning("Aucun fichier trouvé dans le projet.")
                return

            # Générer le prompt d'analyse du projet
            self.ui.print_info(f"Génération du prompt d'analyse pour {len(files)} fichiers...")
            prompt = project_analyzer.generate_project_summary_prompt()

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse du projet", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Afficher la réponse
            self.ui.print_assistant_response(response, args.raw)

            # Déterminer le dossier de sortie
            output_dir = None
            if hasattr(args, 'output_dir') and args.output_dir:
                output_dir = args.output_dir
            elif hasattr(self.config, 'ANALYSIS_DIR'):
                output_dir = self.config.ANALYSIS_DIR

            # Créer le dossier de sortie s'il existe et n'existe pas déjà
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Sauvegarder la réponse
            if hasattr(args, 'output') and args.output:
                # Si output_dir est spécifié et args.output n'est pas un chemin absolu, combiner les deux
                if output_dir and not os.path.isabs(args.output):
                    output_file = os.path.join(output_dir, args.output)
                else:
                    output_file = args.output

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")
            else:
                # Générer un nom de fichier basé sur le répertoire du projet
                project_name = os.path.basename(os.path.abspath(project_dir))
                timestamp = time.strftime("%Y%m%d%H%M%S")

                # Si output_dir est spécifié, l'utiliser; sinon, utiliser le répertoire courant
                if output_dir:
                    output_file = os.path.join(output_dir, f"{project_name}_analysis_{timestamp}.md")
                else:
                    output_file = f"{project_name}_analysis_{timestamp}.md"

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")

            return response

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse du projet: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
            return None

    async def _analyze_patterns(self, args, api_key):
        """Analyse les design patterns dans un fichier de code"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        file_path = args.patterns_analyze
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)
            if not self.client:
                self.ui.print_error("Impossible d'initialiser le client Anthropic. Vérifiez votre clé API.")
                return

        try:
            # Charger le fichier
            file_info = self.pattern_analyzer.load_file(file_path)
            self.ui.print_info(f"Analyse des patterns dans: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Analyser les patterns
            patterns_results = self.pattern_analyzer.detect_patterns_in_file()
            
            # Afficher les résultats initiaux
            detected_patterns = patterns_results['detected_patterns']
            if detected_patterns:
                self.ui.print_success(f"Patterns détectés ({len(detected_patterns)}):")
                for pattern in detected_patterns:
                    self.ui.console.print(f"[bold green]• {pattern['name']}[/bold green]: {pattern['description']}")
            else:
                self.ui.print_warning("Aucun pattern clairement identifié dans ce fichier.")
                
            # Afficher les suggestions
            suggested_patterns = patterns_results['suggested_patterns']
            if suggested_patterns:
                self.ui.print_info(f"Suggestions de patterns ({len(suggested_patterns)}):")
                for pattern in suggested_patterns:
                    self.ui.console.print(f"[bold blue]• {pattern['name']}[/bold blue]: {pattern['description']}")
            
            # Générer le prompt pour une analyse plus approfondie
            prompt = self.pattern_analyzer.generate_pattern_analysis_prompt()
            
            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse des patterns", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Afficher la réponse
            self.ui.print_assistant_response(response, False)
            
            # Sauvegarder la réponse si demandé
            if args.pattern_output:
                with open(args.pattern_output, 'w', encoding='utf-8') as f:
                    f.write(f"# Analyse des patterns de conception dans {file_path}\n\n")
                    
                    # Écrire les patterns détectés
                    f.write("## Patterns détectés\n\n")
                    if detected_patterns:
                        for pattern in detected_patterns:
                            f.write(f"- **{pattern['name']}**: {pattern['description']}\n")
                    else:
                        f.write("Aucun pattern clairement identifié.\n")
                    
                    # Écrire les suggestions
                    f.write("\n## Suggestions de patterns\n\n")
                    if suggested_patterns:
                        for pattern in suggested_patterns:
                            f.write(f"- **{pattern['name']}**: {pattern['description']}\n")
                    else:
                        f.write("Aucune suggestion de pattern.\n")
                    
                    # Écrire l'analyse détaillée
                    f.write("\n## Analyse détaillée\n\n")
                    f.write(response)
                
                self.ui.print_success(f"Analyse sauvegardée dans: {args.pattern_output}")

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse des patterns: {str(e)}")
            if hasattr(args, 'debug') and args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())

    async def _analyze_project_patterns(self, args, api_key):
        """Analyse les design patterns dans un projet entier"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        project_dir = args.project_patterns
        if not os.path.isdir(project_dir):
            self.ui.print_error(f"Le répertoire {project_dir} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)
            if not self.client:
                self.ui.print_error("Impossible d'initialiser le client Anthropic. Vérifiez votre clé API.")
                return

        try:
            # Créer l'analyseur de projet
            from src.code_analysis import ProjectAnalyzer
            project_analyzer = ProjectAnalyzer(project_dir, self.ui.console)
            
            # Configurer les exclusions
            if hasattr(args, 'exclude_dirs') and args.exclude_dirs:
                exclude_dirs = args.exclude_dirs.split(',')
                project_analyzer.add_exclude_dirs(exclude_dirs)
                
            if hasattr(args, 'exclude_files') and args.exclude_files:
                exclude_files = args.exclude_files.split(',')
                project_analyzer.add_exclude_files(exclude_files)
                
            if hasattr(args, 'extensions') and args.extensions:
                extensions = args.extensions.split(',')
                project_analyzer.set_extensions(extensions)
                
            if hasattr(args, 'no_default_excludes') and args.no_default_excludes:
                project_analyzer.use_default_excludes = False
            
            # Configurer l'analyseur de patterns
            self.pattern_analyzer.set_project_analyzer(project_analyzer)
            
            # Scanner le projet
            self.ui.print_info(f"Analyse des patterns dans le projet: {project_dir}")
            with self.ui.create_progress() as progress:
                task = progress.add_task("Scan du projet", total=None)
                project_analyzer.scan_project()
                
            # Analyser les patterns
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse des patterns", total=None)
                project_results = self.pattern_analyzer.analyze_project_patterns()
            
            # Afficher les résultats
            files_analyzed = project_results['files_analyzed']
            files_with_patterns = len(project_results['files_with_patterns'])
            self.ui.print_success(f"Analyse terminée: {files_analyzed} fichiers analysés, {files_with_patterns} avec des patterns")
            
            # Afficher les patterns détectés
            detected_patterns = project_results['detected_patterns']
            if detected_patterns:
                self.ui.print_info(f"Patterns détectés dans le projet:")
                for name, data in detected_patterns.items():
                    self.ui.console.print(f"[bold green]• {name}[/bold green] ({data['count']} fichiers)")
            else:
                self.ui.print_warning("Aucun pattern clairement identifié dans ce projet.")
                
            # Afficher l'aperçu architectural
            if project_results['architectural_overview']:
                self.ui.print_info("Aperçu architectural:")
                for insight in project_results['architectural_overview']:
                    self.ui.console.print(f"[italic]• {insight}[/italic]")
            
            # Générer le prompt pour une analyse approfondie
            prompt = self.pattern_analyzer.generate_project_patterns_prompt()
            
            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse architecturale", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Afficher la réponse
            self.ui.print_assistant_response(response, False)
            
            # Sauvegarder la réponse si demandé
            if args.pattern_output:
                with open(args.pattern_output, 'w', encoding='utf-8') as f:
                    f.write(f"# Analyse des patterns de conception du projet {project_dir}\n\n")
                    
                    # Écrire les statistiques
                    f.write("## Statistiques\n\n")
                    f.write(f"- Fichiers analysés: {files_analyzed}\n")
                    f.write(f"- Fichiers avec patterns: {files_with_patterns}\n\n")
                    
                    # Écrire les patterns détectés
                    f.write("## Patterns détectés\n\n")
                    if detected_patterns:
                        for name, data in detected_patterns.items():
                            f.write(f"- **{name}** ({data['count']} fichiers): {data['description']}\n")
                            f.write("  - Fichiers: " + ", ".join(data['files'][:5]))
                            if len(data['files']) > 5:
                                f.write(f" et {len(data['files']) - 5} autres")
                            f.write("\n")
                    else:
                        f.write("Aucun pattern clairement identifié.\n")
                    
                    # Écrire l'aperçu architectural
                    f.write("\n## Aperçu architectural\n\n")
                    for insight in project_results['architectural_overview']:
                        f.write(f"- {insight}\n")
                    
                    # Écrire l'analyse détaillée
                    f.write("\n## Analyse détaillée\n\n")
                    f.write(response)
                
                self.ui.print_success(f"Analyse sauvegardée dans: {args.pattern_output}")

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse des patterns du projet: {str(e)}")
            if hasattr(args, 'debug') and args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())

    async def run(self):
        """Point d'entrée principal de l'application"""
        args = self.parser.parse_args()

        # Afficher la version et quitter
        if args.version:
            self.ui.print_info(f"Ayla CLI v{self.config.VERSION}")
            return

        # Démarrer le mode setup
        if args.setup:
            setup = AylaSetupAssistant(self.ui, self.config)
            await setup.start()
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

        # Initialiser le gestionnaire d'analyse de code si disponible
        if self.code_analysis_available:
            from src.code_analysis import CodeAnalyzer, PatternAnalyzer
            self.code_analyzer = CodeAnalyzer(self.ui.console)
            self.pattern_analyzer = PatternAnalyzer(self.ui.console)

        # Continuer la dernière conversation si demandé
        if args.continue_conversation:
            last_id = self.conv_manager.get_last_conversation_id()
            if last_id:
                args.conversation_id = last_id
                self.ui.print_info(f"Continuation de la conversation {last_id}")
            else:
                self.ui.print_warning("Aucune conversation précédente trouvée.")

        # Traiter les commandes Git en priorité
        if await self._process_git_commands(args, api_key):
            return

        # Choisir l'action en fonction des arguments
        if args.tui:
            # Lancer l'interface TUI
            tui = TUIManager(self)
            await tui.start(args, api_key)

        elif args.analyze:
            # Analyser un fichier de code
            await self._analyze_code(args, api_key)

        elif args.document:
            # Générer de la documentation
            await self._generate_documentation(args, api_key)

        elif args.project:
            # Analyser un projet entier
            await self._analyze_project(args, api_key)
            
        elif args.patterns_analyze:
            # Analyser les design patterns dans un fichier
            await self._analyze_patterns(args, api_key)
            
        elif args.project_patterns:
            # Analyser les design patterns dans un projet
            await self._analyze_project_patterns(args, api_key)

        else:
            # Traiter une requête standard
            await self._process_request(args, api_key)

    def execute_tui_command(self, command, args):
        """Exécute une commande depuis le TUI et renvoie le résultat"""
        # Imports locaux pour éviter les problèmes de portée
        import asyncio
        import time
        import traceback

        parser_args = argparse.Namespace()

        # Paramètres de base toujours nécessaires
        parser_args.debug = False  # Par défaut pas de debug en mode TUI
        parser_args.stream = True  # Streaming par défaut en mode TUI
        parser_args.raw = False  # Pas de mode raw en TUI
        parser_args.model = self.config.get_model()  # Modèle par défaut
        parser_args.max_tokens = self.config.get_max_tokens()  # Tokens par défaut
        parser_args.temperature = self.config.get_temperature()  # Température par défaut
        parser_args.api_key = None  # Initialiser api_key à None (sera défini par _get_api_key)

        # Paramètres optionnels avec valeurs par défaut pour éviter les erreurs AttributeError
        parser_args.output = None
        parser_args.auto_save = False
        parser_args.file = None
        parser_args.prompt = []
        parser_args.conversation_id = None
        parser_args.continue_conversation = False
        parser_args.interactive = False
        parser_args.timeout = 120
        parser_args.analyze = None
        parser_args.document = None
        parser_args.project = None
        parser_args.analysis_type = "general"
        parser_args.doc_type = "complete"
        parser_args.doc_format = "markdown"

        # Paramètres spécifiques à l'analyse de code (si nécessaire)
        if self.code_analysis_available:
            parser_args.extensions = None
            parser_args.exclude_dirs = None
            parser_args.exclude_files = None
            parser_args.no_default_excludes = False
            parser_args.output_dir = self.config.DEFAULT_ANALYSIS_DIR

        # Obtenir la clé API avant tout traitement pour éviter les erreurs
        try:
            # Obtenir la clé API en premier pour s'assurer qu'elle est disponible
            api_key = self._get_api_key(parser_args)
        except Exception as e:
            return f"Erreur lors de l'obtention de la clé API: {str(e)}"

        # Traiter les différentes commandes
        if command == '/analyze':
            if not args:
                return "Erreur: Veuillez spécifier un fichier à analyser."

            parts = args.split()
            file_path = parts[0]

            if not os.path.exists(file_path):
                return f"Erreur: Le fichier {file_path} n'existe pas."

            parser_args.analyze = file_path

            if len(parts) > 1:
                parser_args.analysis_type = parts[1]

            try:
                # Utiliser la même approche que pour l'analyse
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                    except ImportError:
                        return f"Erreur: Impossible d'analyser le fichier dans le contexte TUI. Utilisez la commande en ligne."

                # Maintenant, nous pouvons exécuter notre coroutine
                analysis_result = loop.run_until_complete(self._analyze_code(parser_args, api_key))

                return f"Analyse du fichier {file_path} terminée."
            except Exception as e:
                with open("tui_command_error.log", "a") as f:
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Command: {command} {args}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(traceback.format_exc())

                return f"Erreur lors de l'analyse: {str(e)}"

        elif command == '/document':
            if not args:
                return "Erreur: Veuillez spécifier un fichier à documenter."

            parts = args.split()
            file_path = parts[0]

            if not os.path.exists(file_path):
                return f"Erreur: Le fichier {file_path} n'existe pas."

            parser_args.document = file_path

            if len(parts) > 1:
                parser_args.doc_type = parts[1]

            try:
                # Utiliser la même approche que pour l'analyse
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                    except ImportError:
                        return f"Erreur: Impossible de générer la documentation dans le contexte TUI. Utilisez la commande en ligne."

                doc_result = loop.run_until_complete(self._generate_documentation(parser_args, api_key))

                return f"Documentation du fichier {file_path} terminée."
            except Exception as e:
                with open("tui_command_error.log", "a") as f:
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Command: {command} {args}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(traceback.format_exc())

                return f"Erreur lors de la génération de documentation: {str(e)}"

        elif command == '/models':
            try:
                models_info = []
                for model, description in self.config.AVAILABLE_MODELS.items():
                    models_info.append(f"{model}: {description}")
                return "\n".join(models_info)
            except Exception as e:
                return f"Erreur lors de la récupération des modèles: {str(e)}"

        elif command == '/project':
            if not args:
                return "Erreur: Veuillez spécifier un répertoire de projet à analyser."

            project_dir = args.split()[0]

            if not os.path.isdir(project_dir):
                return f"Erreur: Le répertoire {project_dir} n'existe pas."

            parser_args.project = project_dir

            try:
                # Utiliser la même approche que pour l'analyse
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                    except ImportError:
                        return f"Erreur: Impossible d'analyser le projet dans le contexte TUI. Utilisez la commande en ligne."

                project_result = loop.run_until_complete(self._analyze_project(parser_args, api_key))

                return f"Analyse du projet {project_dir} terminée."
            except Exception as e:
                with open("tui_command_error.log", "a") as f:
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Command: {command} {args}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(traceback.format_exc())

                return f"Erreur lors de l'analyse du projet: {str(e)}"

        elif command == '/history':
            # Charger l'historique de la conversation actuelle
            if hasattr(self, 'current_conversation_id') and self.current_conversation_id:
                try:
                    history = self.conv_manager.load_conversation_history(self.current_conversation_id)
                    history_text = []
                    for i, msg in enumerate(history):
                        role = "Vous" if msg["role"] == "user" else "Ayla"
                        content = msg["content"]
                        # Limiter la longueur pour l'affichage TUI
                        if len(content) > 100:
                            content = content[:97] + "..."
                        history_text.append(f"{i + 1}. {role}: {content}")
                    return "\n".join(history_text)
                except Exception as e:
                    return f"Erreur lors du chargement de l'historique: {str(e)}"
            return "Aucune conversation active."

        elif command == '/list':
            try:
                conversations = self.conv_manager.list_conversations()
                if not conversations:
                    return "Aucune conversation sauvegardée."

                conv_list = ["Conversations sauvegardées:"]
                for i, conv in enumerate(conversations):
                    conv_list.append(f"{i + 1}. {conv['id']} - {conv['title']} ({conv['messages']} messages)")
                return "\n".join(conv_list)
            except Exception as e:
                return f"Erreur lors de la liste des conversations: {str(e)}"

        elif command == '/load':
            if not args:
                return "Erreur: Veuillez spécifier l'ID de la conversation à charger."

            conversation_id = args.strip()
            try:
                history = self.conv_manager.load_conversation_history(conversation_id)

                if not history:
                    return f"Erreur: Conversation {conversation_id} introuvable ou vide."

                self.current_conversation = history
                self.current_conversation_id = conversation_id
                return f"Conversation {conversation_id} chargée avec {len(history)} messages."
            except Exception as e:
                return f"Erreur lors du chargement de la conversation: {str(e)}"

        elif command == '/save':
            if not hasattr(self, 'current_conversation') or not self.current_conversation:
                return "Erreur: Aucune conversation active à sauvegarder."

            try:
                if args:
                    conversation_id = args.strip()
                else:
                    # Utiliser le time déjà importé au début de la fonction
                    conversation_id = time.strftime("%Y%m%d%H%M%S")

                self.conv_manager.save_conversation_history(conversation_id, self.current_conversation)
                self.current_conversation_id = conversation_id
                return f"Conversation sauvegardée avec l'ID: {conversation_id}"
            except Exception as e:
                return f"Erreur lors de la sauvegarde de la conversation: {str(e)}"
        elif command == '/git-status':
            try:
                self.git_manager.set_repo_path(os.getcwd())
                self.git_manager.refresh_repo_info()

                repo_info = self.git_manager.repo_info
                status_text = []

                if 'branch' in repo_info:
                    status_text.append(f"Branche: {repo_info['branch']}")

                if 'status' in repo_info:
                    status = repo_info['status']
                    if status['is_clean']:
                        status_text.append("Dépôt propre (aucune modification)")
                    else:
                        if status['modified']:
                            status_text.append(f"Fichiers modifiés: {len(status['modified'])}")
                        if status['untracked']:
                            status_text.append(f"Fichiers non suivis: {len(status['untracked'])}")
                        if status['staged']:
                            status_text.append(f"Fichiers indexés: {len(status['staged'])}")

                if 'last_commit' in repo_info:
                    last_commit = repo_info['last_commit']
                    if last_commit and last_commit.get('hash'):
                        status_text.append(f"Dernier commit: {last_commit.get('hash')} - {last_commit.get('message')}")

                return "\n".join(status_text)
            except Exception as e:
                return f"Erreur lors de la récupération du statut Git: {str(e)}"

        elif command == '/git-commit':
            try:
                self.git_manager.set_repo_path(os.getcwd())
                diff_text = self.git_manager.get_detailed_diff()

                if not diff_text or "Aucune différence détectée" in diff_text:
                    return "Aucun changement détecté pour créer un commit"

                # Créer un drapeau pour indiquer à la boucle principale de lancer la tâche
                self.tui_task_queue = {
                    "type": "git_commit",
                    "api_key": api_key,
                    "model": self.config.get_model(),
                    "diff_text": diff_text
                }

                return "Génération du message de commit en cours..."
            except Exception as e:
                return f"Erreur lors de la génération du message de commit: {str(e)}"

        elif command == '/git-conventional':
            try:
                self.git_manager.set_repo_path(os.getcwd())
                diff_text = self.git_manager.get_detailed_diff()

                if not diff_text or "Aucune différence détectée" in diff_text:
                    return "Aucun changement détecté pour créer un commit"

                # Créer un drapeau pour indiquer à la boucle principale de lancer la tâche
                self.tui_task_queue = {
                    "type": "git_conventional",
                    "api_key": api_key,
                    "model": self.config.get_model(),
                    "diff_text": diff_text
                }

                return "Génération du message de commit conventionnel en cours..."
            except Exception as e:
                return f"Erreur lors de la génération du message conventionnel: {str(e)}"

        elif command == '/git-branch':
            if not args:
                return "Veuillez fournir une description pour la branche"

            try:
                self.git_manager.set_repo_path(os.getcwd())

                # Créer un drapeau pour indiquer à la boucle principale de lancer la tâche
                self.tui_task_queue = {
                    "type": "git_branch",
                    "api_key": api_key,
                    "model": self.config.get_model(),
                    "description": args
                }

                return "Génération du nom de branche en cours..."
            except Exception as e:
                return f"Erreur lors de la génération du nom de branche: {str(e)}"
        elif command == '/git-stash':
            if not args:
                return "Erreur: Veuillez spécifier un nom pour le stash"

            stash_name = args.strip()
            success = self.git_manager.stash_changes(name=stash_name if stash_name else None)

            if success:
                self.ui.print_success("Stash créé avec succès")
            else:
                self.ui.print_error("Erreur lors de la création du stash")
        elif command == '/git-stash-apply':
            success = self.git_manager.stash_changes(apply_immediately=True)

            if not success:
                self.ui.print_error("Erreur lors de l'application du stash")
        elif command == '/git-merge':
            if not args:
                return "Erreur: Veuillez spécifier une branche à fusionner"

            source_branch = args.strip()
            success = self.git_manager.merge_branch(source_branch, squash=False)

            if success:
                self.ui.print_success(f"Branche '{source_branch}' fusionnée avec succès")
            else:
                self.ui.print_error("Erreur lors de la fusion de la branche")
        elif command == '/git-merge-squash':
            if not args:
                return "Erreur: Veuillez spécifier une branche à fusionner"

            source_branch = args.strip()
            success = self.git_manager.merge_branch(source_branch, squash=True)

            if success:
                self.ui.print_success(f"Branche '{source_branch}' fusionnée et squashée avec succès")
            else:
                self.ui.print_error("Erreur lors de la fusion et squashing de la branche")
        elif command == '/git-log':
            format_type = args.git_log_format
            count = args.git_log_count
            show_graph = args.git_log_graph

            log_output = self.git_manager.get_enhanced_log(
                format_type=format_type,
                count=count,
                show_graph=show_graph
            )

            self.ui.console.print("\n[bold]Historique Git[/bold]\n")
            self.ui.console.print(log_output)
        elif command == '/git-visualize':
            self._handle_git_visualize(args)
            return True
        elif command == '/git-conflict-assist':
            self._handle_git_conflict_assist(args)
            return True
        elif command == '/git-retrospective':
            self._handle_git_retrospective(args)
            return True
        else:
            return f"Commande {command} non reconnue ou non implémentée."

    async def send_question_to_claude(self, question):
        """Envoie une question à Claude et renvoie la réponse"""
        # Imports nécessaires
        import time
        import traceback

        # Créer les arguments par défaut
        parser_args = argparse.Namespace()

        # Paramètres obligatoires
        parser_args.prompt = question.split()
        parser_args.model = self.config.get_model()
        parser_args.max_tokens = self.config.get_max_tokens()
        parser_args.temperature = self.config.get_temperature()
        parser_args.api_key = None  # Sera défini par _get_api_key

        # Paramètres optionnels
        parser_args.output = None
        parser_args.auto_save = False
        parser_args.raw = False
        parser_args.debug = False
        parser_args.file = None
        parser_args.stream = False  # Dans le TUI on gère différemment le streaming
        parser_args.timeout = 120
        parser_args.conversation_id = None
        parser_args.continue_conversation = False
        parser_args.interactive = False

        # S'assurer que les conversations sont initialisées
        if not hasattr(self, 'current_conversation'):
            self.current_conversation = []

        if not hasattr(self, 'current_conversation_id'):
            # Utiliser time déjà importé au début de la fonction
            self.current_conversation_id = time.strftime("%Y%m%d%H%M%S")

        # Ajouter la question à la conversation
        self.current_conversation.append({"role": "user", "content": question})

        try:
            # Obtenir la clé API
            api_key = self._get_api_key(parser_args)
            if not api_key:
                return "Erreur: Aucune clé API disponible. Veuillez configurer votre clé API."

            # Initialiser le client si ce n'est pas déjà fait
            if not self.client:
                self.client = AnthropicClient(api_key)

            # Obtenir la réponse
            response_text = await self.client.send_message(
                parser_args.model,
                self.current_conversation,
                parser_args.max_tokens,
                parser_args.temperature
            )

            # Ajouter la réponse à la conversation
            self.current_conversation.append({"role": "assistant", "content": response_text})

            # Sauvegarder automatiquement la conversation
            try:
                self.conv_manager.save_conversation_history(
                    self.current_conversation_id,
                    self.current_conversation
                )
            except Exception as save_error:
                # Journaliser l'erreur de sauvegarde mais continuer
                with open("conversation_save_error.log", "a") as f:
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Error: {str(save_error)}\n")
                    f.write(traceback.format_exc())

            return response_text

        except Exception as e:
            # Plus de détails pour le débogage
            error_message = f"Erreur lors de l'envoi de la question: {str(e)}"

            # Journaliser l'erreur
            error_details = traceback.format_exc()
            with open("claude_error.log", "a") as f:
                f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(f"Question: {question}\n")
                f.write(f"Error: {str(e)}\n")
                f.write(error_details)

            # Ajouter des informations spécifiques basées sur le type d'erreur
            if "api_key" in str(e):
                error_message += "\nProblème avec la clé API. Veuillez vérifier votre configuration."
            elif "timeout" in str(e).lower():
                error_message += "\nLa requête a pris trop de temps. Essayez avec un message plus court."
            elif "rate_limit" in str(e).lower():
                error_message += "\nLimite de requêtes atteinte. Veuillez attendre un moment avant de réessayer."

            return error_message

    async def _process_git_commands(self, args, api_key):
        """Traite les commandes Git"""
        # Vérifier si une commande Git est demandée
        has_git_command = any([
            hasattr(args, 'git_commit') and args.git_commit,
            hasattr(args, 'git_branch') and args.git_branch,
            hasattr(args, 'git_analyze') and args.git_analyze,
            hasattr(args, 'git_diff_analyze') and args.git_diff_analyze,
            hasattr(args, 'git_create_branch') and args.git_create_branch,
            hasattr(args, 'git_commit_and_push') and args.git_commit_and_push,
            hasattr(args, 'git_conventional_commit') and args.git_conventional_commit,
            hasattr(args, 'git_stash') and args.git_stash is not None,
            hasattr(args, 'git_stash_apply') and args.git_stash_apply,
            hasattr(args, 'git_merge') and args.git_merge,
            hasattr(args, 'git_merge_squash') and args.git_merge_squash,
            hasattr(args, 'git_log') and args.git_log,
            hasattr(args, 'git_visualize') and args.git_visualize,
            hasattr(args, 'git_conflict_assist') and args.git_conflict_assist,
            hasattr(args, 'git_retrospective') and args.git_retrospective is not None
        ])
        
        if not has_git_command:
            return False
            
        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)
            
        # S'assurer que des valeurs par défaut sont définies pour les commandes qui en ont besoin
        if not hasattr(args, 'model'):
            args.model = self.config.DEFAULT_MODEL
        if not hasattr(args, 'max_tokens'):
            args.max_tokens = self.config.DEFAULT_MAX_TOKENS
        if not hasattr(args, 'temperature'):
            args.temperature = self.config.DEFAULT_TEMPERATURE
        if not hasattr(args, 'interactive'):
            args.interactive = True
            
        # Configurer le répertoire Git
        repo_path = args.git_repo if hasattr(args, 'git_repo') and args.git_repo else os.getcwd()
        if not self.git_manager.set_repo_path(repo_path):
            self.ui.print_error(f"Le répertoire {repo_path} n'est pas un dépôt Git valide")
            return True
        
        # Traiter la commande git-commit
        if hasattr(args, 'git_commit') and args.git_commit:
            await self._handle_git_commit(args)
            return True
            
        # Traiter la commande git-branch
        if hasattr(args, 'git_branch') and args.git_branch:
            await self._handle_git_branch(args)
            return True
            
        # Traiter la commande git-analyze
        if hasattr(args, 'git_analyze') and args.git_analyze:
            self._handle_git_analyze()
            return True
            
        # Traiter la commande git-diff-analyze
        if hasattr(args, 'git_diff_analyze') and args.git_diff_analyze:
            await self._handle_git_diff_analyze(args)
            return True
            
        # Traiter la commande git-create-branch
        if hasattr(args, 'git_create_branch') and args.git_create_branch:
            await self._handle_git_create_branch(args)
            return True
            
        # Traiter la commande git-commit-and-push
        if hasattr(args, 'git_commit_and_push') and args.git_commit_and_push:
            await self._handle_git_commit_and_push(args)
            return True
            
        # Traiter la commande git-conventional-commit
        if hasattr(args, 'git_conventional_commit') and args.git_conventional_commit:
            await self._handle_git_conventional_commit(args)
            return True
            
        # Traiter la commande git-stash
        if hasattr(args, 'git_stash') and args.git_stash is not None:
            self._handle_git_stash(args)
            return True
            
        # Traiter la commande git-stash-apply
        if hasattr(args, 'git_stash_apply') and args.git_stash_apply:
            self._handle_git_stash_apply(args)
            return True
            
        # Traiter la commande git-merge
        if hasattr(args, 'git_merge') and args.git_merge:
            self._handle_git_merge(args, squash=False)
            return True
            
        # Traiter la commande git-merge-squash
        if hasattr(args, 'git_merge_squash') and args.git_merge_squash:
            self._handle_git_merge(args, squash=True)
            return True
            
        # Traiter la commande git-log
        if hasattr(args, 'git_log') and args.git_log:
            self._handle_git_log(args)
            return True
            
        # Traiter la commande git-visualize
        if hasattr(args, 'git_visualize') and args.git_visualize:
            self._handle_git_visualize(args)
            return True
            
        # Traiter la commande git-conflict-assist
        if hasattr(args, 'git_conflict_assist') and args.git_conflict_assist:
            self._handle_git_conflict_assist(args)
            return True
            
        # Traiter la commande git-retrospective
        if hasattr(args, 'git_retrospective') and args.git_retrospective is not None:
            self._handle_git_retrospective(args)
            return True
            
        return False

    async def _handle_git_commit(self, args):
        """Génère un message de commit intelligent pour les changements actuels"""
        # Obtenir le diff des changements
        diff_text = self.git_manager.get_detailed_diff()

        if "Aucune différence détectée" in diff_text or not diff_text:
            self.ui.print_warning("Aucun changement détecté pour créer un commit")
            return

        # Générer un message de commit intelligent avec Claude
        self.ui.print_info("Génération d'un message de commit intelligent...")

        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse des changements", total=None)
            commit_message = await self.git_manager.generate_commit_message_with_claude(
                diff_text,
                self.client,
                args.model
            )

        # Afficher le message généré
        self.ui.print_success("Message de commit généré :")
        self.ui.console.print(f"\n[bold cyan]{commit_message}[/bold cyan]\n")

        # Demander confirmation pour créer le commit
        if args.interactive:
            confirm = self.ui.get_input("Voulez-vous créer un commit avec ce message? (o/n): ").lower()
            if confirm in ('o', 'oui'):
                success = self.git_manager.commit_changes(commit_message)
                if success:
                    self.ui.print_success("Commit créé avec succès")
            else:
                self.ui.print_info("Commit annulé par l'utilisateur")

    async def _handle_git_branch(self, args):
        """Suggère un nom de branche intelligent basé sur la description fournie"""
        description = args.git_branch

        if not description:
            self.ui.print_error("Veuillez fournir une description pour la branche")
            return

        # Générer un nom de branche intelligent avec Claude
        self.ui.print_info("Génération d'un nom de branche intelligent...")

        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse de la description", total=None)
            branch_name = await self.git_manager.suggest_branch_name_with_claude(
                description,
                self.client,
                args.model
            )

        # Afficher le nom de branche suggéré
        self.ui.print_success("Nom de branche suggéré :")
        self.ui.console.print(f"\n[bold cyan]{branch_name}[/bold cyan]\n")

        # Demander confirmation pour créer la branche
        if args.interactive:
            confirm = self.ui.get_input("Voulez-vous créer cette branche? (o/n): ").lower()
            if confirm in ('o', 'oui'):
                success = self.git_manager.switch_branch(branch_name, create=True)
                if success:
                    self.ui.print_success(f"Branche {branch_name} créée et activée")
            else:
                self.ui.print_info("Création de branche annulée par l'utilisateur")
        else:
            # En mode non interactif, créer la branche directement
            success = self.git_manager.switch_branch(branch_name, create=True)
            if success:
                self.ui.print_success(f"Branche {branch_name} créée et activée")

    def _handle_git_analyze(self):
        """Analyse le dépôt Git et fournit des insights"""
        # Analyser le dépôt
        self.ui.print_info("Analyse du dépôt Git...")
        analysis = self.git_manager.analyze_repo()

        # Afficher l'analyse
        self.ui.console.print("\n[bold]Analyse du dépôt Git[/bold]")

        # Afficher les informations de base
        if 'repo_info' in analysis:
            repo_info = analysis['repo_info']
            self.ui.console.print(f"\n[cyan]Branche actuelle:[/cyan] {repo_info.get('branch', 'inconnue')}")

            # Afficher le dernier commit
            last_commit = repo_info.get('last_commit', {})
            if last_commit and last_commit.get('hash'):
                self.ui.console.print(
                    f"\n[cyan]Dernier commit:[/cyan] {last_commit.get('hash')} - "
                    f"{last_commit.get('message')} "
                    f"par {last_commit.get('author')} "
                    f"({last_commit.get('date')})"
                )

            # Afficher le statut
            status = repo_info.get('status', {})
            if status:
                if status.get('is_clean'):
                    self.ui.console.print("\n[green]Le dépôt est propre (aucun changement)[/green]")
                else:
                    self.ui.console.print("\n[yellow]Le dépôt contient des changements:[/yellow]")
                    if status.get('modified'):
                        self.ui.console.print(f"  - {len(status['modified'])} fichiers modifiés")
                    if status.get('untracked'):
                        self.ui.console.print(f"  - {len(status['untracked'])} fichiers non suivis")
                    if status.get('staged'):
                        self.ui.console.print(f"  - {len(status['staged'])} fichiers indexés pour commit")

        # Afficher les statistiques de commits
        if 'commit_stats' in analysis:
            commit_stats = analysis['commit_stats']
            self.ui.console.print(f"\n[cyan]Total des commits:[/cyan] {commit_stats.get('total_commits', 0)}")

            # Afficher les auteurs
            authors = commit_stats.get('authors', {})
            if authors:
                self.ui.console.print("\n[cyan]Contributeurs:[/cyan]")
                for author, count in authors.items():
                    self.ui.console.print(f"  - {author}: {count} commits")

        # Afficher les insights
        if 'insights' in analysis and analysis['insights']:
            self.ui.console.print("\n[bold cyan]Insights:[/bold cyan]")
            for insight in analysis['insights']:
                self.ui.console.print(f"  • {insight}")

        self.ui.console.print()

    async def _handle_git_diff_analyze(self, args):
        """Analyse détaillée des changements actuels"""
        # Obtenir le diff des changements
        diff_text = self.git_manager.get_detailed_diff()

        if "Aucune différence détectée" in diff_text or not diff_text:
            self.ui.print_warning("Aucun changement détecté à analyser")
            return

        # Analyser les changements avec Claude
        self.ui.print_info("Analyse détaillée des changements avec Claude...")

        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse des changements", total=None)
            analysis = await self.git_manager.analyze_code_changes_with_claude(
                diff_text,
                self.client,
                args.model
            )

        # Afficher l'analyse
        self.ui.console.print("\n[bold]Analyse des changements[/bold]")

        if 'summary' in analysis:
            self.ui.console.print(f"\n[cyan]Résumé:[/cyan] {analysis['summary']}")

        if 'impact' in analysis:
            impact = analysis['impact']
            impact_color = "green" if impact == "Minimal" else "yellow" if impact == "Modéré" else "red"
            self.ui.console.print(f"\n[cyan]Impact:[/cyan] [{impact_color}]{impact}[/{impact_color}]")

        if 'type_changes' in analysis and analysis['type_changes']:
            self.ui.console.print("\n[cyan]Types de changements:[/cyan]")
            for change_type in analysis['type_changes']:
                self.ui.console.print(f"  • {change_type}")

        if 'affected_components' in analysis and analysis['affected_components']:
            self.ui.console.print("\n[cyan]Composants affectés:[/cyan]")
            for component in analysis['affected_components']:
                self.ui.console.print(f"  • {component}")

        if 'potential_issues' in analysis and analysis['potential_issues']:
            self.ui.console.print("\n[yellow]Problèmes potentiels:[/yellow]")
            for issue in analysis['potential_issues']:
                self.ui.console.print(f"  • {issue}")

        if 'recommendations' in analysis and analysis['recommendations']:
            self.ui.console.print("\n[green]Recommandations:[/green]")
            for recommendation in analysis['recommendations']:
                self.ui.console.print(f"  • {recommendation}")

        self.ui.console.print()

    async def _handle_git_create_branch(self, args):
        """Crée une nouvelle branche avec un nom intelligent"""
        # Demander une description de la tâche si en mode interactif
        description = " ".join(args.prompt) if args.prompt else None

        if not description and args.interactive:
            description = self.ui.get_input("Veuillez décrire la tâche pour cette branche: ")

        if not description:
            self.ui.print_error("Veuillez fournir une description pour la branche")
            return

        # Générer un nom de branche intelligent avec Claude
        self.ui.print_info("Génération d'un nom de branche intelligent...")

        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse de la description", total=None)
            branch_name = await self.git_manager.suggest_branch_name_with_claude(
                description,
                self.client,
                args.model
            )

        # Afficher le nom de branche suggéré
        self.ui.print_success("Nom de branche suggéré :")
        self.ui.console.print(f"\n[bold cyan]{branch_name}[/bold cyan]\n")

        # Demander confirmation pour créer la branche
        if args.interactive:
            confirm = self.ui.get_input("Voulez-vous créer cette branche? (o/n): ").lower()
            if confirm in ('o', 'oui'):
                success = self.git_manager.switch_branch(branch_name, create=True)
                if success:
                    self.ui.print_success(f"Branche {branch_name} créée et activée")
            else:
                self.ui.print_info("Création de branche annulée par l'utilisateur")
        else:
            # En mode non interactif, créer la branche directement
            success = self.git_manager.switch_branch(branch_name, create=True)
            if success:
                self.ui.print_success(f"Branche {branch_name} créée et activée")

    async def _handle_git_commit_and_push(self, args):
        """Commit les changements avec un message intelligent et pousse vers le remote"""
        # S'assurer que nous avons un client API
        api_key = self._get_api_key(args)
        if not api_key:
            self.ui.print_error("Aucune clé API disponible. Veuillez configurer votre clé API.")
            return
            
        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(api_key)
            if not self.client:
                self.ui.print_error("Impossible d'initialiser le client Anthropic. Vérifiez votre clé API.")
                return
        
        # Obtenir le diff des changements
        diff_text = self.git_manager.get_detailed_diff()
        
        if "Aucune différence détectée" in diff_text or not diff_text:
            self.ui.print_warning("Aucun changement détecté pour créer un commit")
            return
        
        # Générer un message de commit intelligent avec Claude
        self.ui.print_info("Génération d'un message de commit intelligent...")
        
        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse des changements", total=None)
            commit_message = await self.git_manager.generate_commit_message_with_claude(
                diff_text,
                self.client,
                args.model
            )
        
        # Afficher le message généré
        self.ui.print_success("Message de commit suggéré :")
        self.ui.console.print(f"\n[italic]{commit_message}[/italic]\n")
        
        # Demander confirmation pour créer le commit et pousser
        if args.interactive:
            confirm = self.ui.get_input("Voulez-vous créer un commit et pousser avec ce message? (o/n): ").lower()
            if confirm in ('o', 'oui'):
                # Créer le commit
                success = self.git_manager.commit_changes(commit_message)
                if success:
                    self.ui.print_success("Commit créé avec succès")
                    
                    # Pousser vers le remote
                    push_success = self.git_manager.push_changes()
                    if push_success:
                        self.ui.print_success("Changements poussés avec succès")
                    else:
                        self.ui.print_error("Erreur lors du push des changements")
                else:
                    self.ui.print_error("Erreur lors de la création du commit")
            else:
                self.ui.print_info("Commit et push annulés par l'utilisateur")
        else:
            # En mode non interactif, créer le commit et pousser directement
            success = self.git_manager.commit_changes(commit_message)
            if success:
                self.ui.print_success("Commit créé avec succès")
                
                # Pousser vers le remote
                push_success = self.git_manager.push_changes()
                if push_success:
                    self.ui.print_success("Changements poussés avec succès")
                else:
                    self.ui.print_error("Erreur lors du push des changements")
            else:
                self.ui.print_error("Erreur lors de la création du commit")

    async def _handle_git_conventional_commit(self, args):
        """Génère un message de commit au format Conventional Commits"""
        # Obtenir le diff des changements
        diff_text = self.git_manager.get_detailed_diff()

        if "Aucune différence détectée" in diff_text or not diff_text:
            self.ui.print_warning("Aucun changement détecté pour créer un commit")
            return

        # Générer un message de commit intelligent avec Claude
        self.ui.print_info("Génération d'un message de commit conventionnel...")

        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse des changements", total=None)
            commit_data = await self.git_manager.generate_conventional_commit(
                diff_text,
                self.client,
                args.model
            )

        # Afficher le message généré avec une mise en forme appropriée
        self.ui.display_conventional_commit(commit_data)

        # Récupérer le message formaté pour le commit
        commit_message = commit_data.get('formatted', "chore: Mise à jour du code")

        # Demander confirmation pour créer le commit
        if args.interactive:
            confirm = self.ui.get_input("Voulez-vous créer un commit avec ce message? (o/n): ").lower()
            if confirm in ('o', 'oui'):
                success = self.git_manager.commit_changes(commit_message)
                if success:
                    self.ui.print_success("Commit créé avec succès")
            else:
                self.ui.print_info("Commit annulé par l'utilisateur")
        else:
            # En mode non interactif, créer le commit directement
            success = self.git_manager.commit_changes(commit_message)
            if success:
                self.ui.print_success("Commit créé avec succès")

    def _handle_git_stash(self, args):
        """Crée un stash des modifications courantes"""
        stash_name = args.git_stash
        success = self.git_manager.stash_changes(name=stash_name if stash_name else None)

        if success:
            self.ui.print_success("Stash créé avec succès")

    def _handle_git_stash_apply(self, args):
        """Applique le dernier stash créé"""
        # Pour simplifier, on va créer un stash et l'appliquer immédiatement
        success = self.git_manager.stash_changes(apply_immediately=True)

        if not success:
            self.ui.print_error("Erreur lors de l'application du stash")

    def _handle_git_merge(self, args, squash=False):
        """Fusionne la branche spécifiée dans la branche courante"""
        source_branch = args.git_merge if not squash else args.git_merge_squash

        if not source_branch:
            self.ui.print_error("Veuillez spécifier une branche source à fusionner")
            return

        # Demander confirmation pour la fusion
        if args.interactive:
            target_branch = self.git_manager.current_branch
            action = "fusionner et squasher" if squash else "fusionner"
            confirm = self.ui.get_input(
                f"Voulez-vous {action} la branche '{source_branch}' dans '{target_branch}'? (o/n): "
            ).lower()

            if confirm not in ('o', 'oui'):
                self.ui.print_info("Fusion annulée par l'utilisateur")
                return

        # Exécuter la fusion
        success = self.git_manager.merge_branch(source_branch, squash=squash)

        if success:
            action = "fusionnée et squasher" if squash else "fusionnée"
            self.ui.print_success(f"Branche '{source_branch}' {action} avec succès")

    def _handle_git_log(self, args):
        """Affiche un historique Git amélioré"""
        format_type = args.git_log_format
        count = args.git_log_count
        show_graph = args.git_log_graph

        # Récupérer et afficher le log
        log_output = self.git_manager.get_enhanced_log(
            format_type=format_type,
            count=count,
            show_graph=show_graph
        )

        # Afficher le résultat
        self.ui.console.print("\n[bold]Historique Git[/bold]\n")
        self.ui.console.print(log_output)

    def _handle_git_visualize(self, args):
        """Affiche une visualisation avancée de l'historique Git"""
        # Vérifier si nous avons accès au répertoire Git
        if not self.git_manager.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return

        # Configurer les options
        max_count = args.git_log_count if hasattr(args, 'git_log_count') else 30
        include_all = True  # Par défaut, on montre toutes les branches
        include_stats = args.git_log_format == 'stats' if hasattr(args, 'git_log_format') else False
        compact = False

        # Générer la visualisation
        self.ui.print_info("Génération de la visualisation de l'historique Git...")
        visualisation = self.git_manager.visualize_git_history(
            max_count=max_count,
            include_all_branches=include_all,
            compact=compact,
            include_stats=include_stats
        )

        # Afficher le résultat
        self.ui.console.print("\n[bold]Visualisation de l'historique Git[/bold]\n")

        # Afficher directement la sortie brute pour préserver la mise en forme
        print(visualisation)

    def _handle_git_conflict_assist(self, args):
        """Fournit une assistance pour résoudre les conflits de fusion"""
        # Vérifier si nous avons accès au répertoire Git
        if not self.git_manager.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return

        # Obtenir la branche source à partir du fichier MERGE_HEAD
        merge_head_path = os.path.join(self.git_manager.repo_path, '.git', 'MERGE_HEAD')
        source_branch = "branche_source"  # Valeur par défaut

        if os.path.exists(merge_head_path):
            try:
                with open(merge_head_path, 'r') as f:
                    merge_head = f.read().strip()

                # Obtenir le nom de la branche à partir du hash
                success, branch_output = self.git_manager._run_git_command(
                    ['name-rev', '--name-only', merge_head]
                )
                if success and branch_output:
                    source_branch = branch_output.replace('remotes/', '').split('~')[0]
            except Exception as e:
                self.ui.print_warning(f"Impossible de déterminer la branche source: {str(e)}")

        # Obtenir l'analyse des conflits
        self.ui.print_info("Analyse des conflits de fusion en cours...")
        conflict_analysis = self.git_manager.assist_merge_conflicts(source_branch)

        # Vérifier s'il y a une erreur
        if "error" in conflict_analysis:
            self.ui.print_error(conflict_analysis["error"])
            return

        # Afficher le résumé des conflits
        self.ui.console.print("\n[bold]Analyse des conflits de fusion[/bold]\n")

        self.ui.console.print(
            f"[cyan]Fusion entre:[/cyan] {conflict_analysis['source_branch']} → "
            f"{conflict_analysis['target_branch']}"
        )

        conflict_count = conflict_analysis["conflict_files_count"]
        self.ui.console.print(f"\n[yellow]Nombre de fichiers en conflit:[/yellow] {conflict_count}")

        # Afficher la liste des fichiers en conflit
        if conflict_count > 0:
            self.ui.console.print("\n[bold]Fichiers en conflit:[/bold]")
            for file_path in conflict_analysis["conflict_files"]:
                self.ui.console.print(f"  - {file_path}")

            # Afficher l'analyse détaillée pour chaque fichier
            self.ui.console.print("\n[bold]Analyse détaillée:[/bold]")
            for file_analysis in conflict_analysis["analysis"]:
                file_path = file_analysis["file"]
                conflicts_count = file_analysis["conflicts_count"]

                self.ui.console.print(f"\n[green]{file_path}[/green] ({conflicts_count} conflits)")

                for i, conflict in enumerate(file_analysis.get("conflicts", [])):
                    conflict_type = conflict["type"]
                    self.ui.console.print(f"  Conflit #{i+1} - Type: {conflict_type}")
                    
                    if conflict_type != "aucun_changement":
                        self.ui.console.print("    [red]Version actuelle:[/red]")
                        current_lines = conflict["current_version"].split("\n")
                        for line in current_lines[:3]:  # Limiter l'affichage
                            self.ui.console.print(f"      {line}")
                        if len(current_lines) > 3:
                            self.ui.console.print("      ...")

                        self.ui.console.print("    [blue]Version entrante:[/blue]")
                        incoming_lines = conflict["incoming_version"].split("\n")
                        for line in incoming_lines[:3]:  # Limiter l'affichage
                            self.ui.console.print(f"      {line}")
                        if len(incoming_lines) > 3:
                            self.ui.console.print("      ...")

                        self.ui.console.print("    [green]Suggestion:[/green]")
                        if "modification_majeure" in conflict_type:
                            self.ui.console.print("      Conflit complexe nécessitant une résolution manuelle")
                        else:
                            suggested_lines = conflict["suggestion"].split("\n")
                            for line in suggested_lines[:3]:  # Limiter l'affichage
                                self.ui.console.print(f"      {line}")
                            if len(suggested_lines) > 3:
                                self.ui.console.print("      ...")

            # Afficher les commandes suggérées
            self.ui.console.print("\n[bold]Commandes utiles:[/bold]")
            for cmd in conflict_analysis["command_suggestions"]:
                self.ui.console.print(f"  {cmd}")

    def _handle_git_retrospective(self, args):
        """Génère une rétrospective basée sur l'activité Git récente"""
        # Vérifier si nous avons accès au répertoire Git
        if not self.git_manager.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return

        # Obtenir la période (nombre de jours)
        days = args.git_retrospective

        # Générer la rétrospective
        self.ui.print_info(f"Génération de la rétrospective sur les {days} derniers jours...")
        with self.ui.create_progress() as progress:
            task = progress.add_task("Analyse de l'activité", total=None)
            retrospective = self.git_manager.generate_sprint_retrospective(
                days=days,
                include_stats=True,
                categorize=True
            )

        # Vérifier s'il y a une erreur
        if "error" in retrospective:
            self.ui.print_error(retrospective["error"])
            return

        # Afficher la rétrospective
        self.ui.console.print("\n[bold]Rétrospective du projet[/bold]\n")

        # Période
        period = retrospective["period"]
        self.ui.console.print(
            f"[cyan]Période:[/cyan] {period['start_date']} → {period['end_date']} "
            f"({period['days']} jours)"
        )

        # Résumé
        summary = retrospective["summary"]
        self.ui.console.print("\n[bold]Résumé de l'activité:[/bold]")
        self.ui.console.print(f"  - Commits totaux: {summary['total_commits']}")
        self.ui.console.print(f"  - Contributeurs actifs: {summary['active_authors']}")
        self.ui.console.print(f"  - Commits par jour en moyenne: {summary['commits_per_day']}")

        # Catégories de commits
        if "categories" in retrospective:
            self.ui.console.print("\n[bold]Répartition par type:[/bold]")
            categories = retrospective["categories"]
            total = sum(categories.values())

            if total > 0:
                for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    percentage = round((count / total) * 100)
                    bar = "█" * int(percentage / 5)
                    self.ui.console.print(
                        f"  - {category}: {count} ({percentage}%) {bar}"
                    )

        # Contributeurs
        authors = retrospective["authors"]
        self.ui.console.print("\n[bold]Contributeurs:[/bold]")
        for author, stats in sorted(
            authors.items(), 
            key=lambda x: x[1]["commit_count"], 
            reverse=True
        ):
            self.ui.console.print(
                f"  - {author}: {stats['commit_count']} commits "
                f"(de {stats['first_commit_date']} à {stats['last_commit_date']})"
            )

        # Statistiques des fichiers
        if "file_stats" in retrospective:
            file_stats = retrospective["file_stats"]
            self.ui.console.print("\n[bold]Statistiques des fichiers:[/bold]")
            self.ui.console.print(f"  - Fichiers modifiés: {file_stats['files_changed']}")

            if "most_changed_files" in file_stats and file_stats["most_changed_files"]:
                self.ui.console.print("\n  [bold]Fichiers les plus modifiés:[/bold]")
                for stat in file_stats["most_changed_files"]:
                    self.ui.console.print(
                        f"    - {stat['file']}: +{stat['additions']}/-{stat['deletions']}"
                    )

            if "summary" in file_stats and file_stats["summary"]:
                self.ui.console.print(f"\n  [bold]Récapitulatif:[/bold] {file_stats['summary']}")

        # Commits récents
        if "commits" in retrospective and retrospective["commits"]:
            self.ui.console.print("\n[bold]Commits récents:[/bold]")
            for commit in retrospective["commits"]:
                self.ui.console.print(
                    f"  - {commit['date']} [{commit['hash']}] {commit['message']} "
                    f"({commit['author']})"
                )

            if retrospective.get("has_more_commits", False):
                self.ui.console.print("  ... et plus encore")

    async def _process_tui_tasks(self):
        """Traite les tâches asynchrones en attente pour le TUI"""
        if not hasattr(self, 'tui_task_queue') or not self.tui_task_queue:
            return

        task_type = self.tui_task_queue.get("type", "")
        api_key = self.tui_task_queue.get("api_key", "")

        if not api_key:
            self._tui_output.add_message("Erreur: Clé API invalide")
            self.tui_task_queue = None
            return

        try:
            if task_type == "git_commit":
                # Traiter la tâche de génération de message de commit
                diff_text = self.tui_task_queue.get("diff_text", "")
                model = self.tui_task_queue.get("model", "")

                client = AnthropicClient(api_key)
                commit_message = await self.git_manager.generate_commit_message_with_claude(
                    diff_text, client, model
                )

                self._tui_output.add_message(f"Message de commit généré: {commit_message}")

                # Demander confirmation
                self._tui_output.add_message("Confirmez-vous la création du commit? (o/n)")
                self._tui_state = "confirm_commit"
                self._tui_commit_message = commit_message

            elif task_type == "git_conventional":
                # Traiter la tâche de génération de message de commit conventionnel
                diff_text = self.tui_task_queue.get("diff_text", "")
                model = self.tui_task_queue.get("model", "")

                client = AnthropicClient(api_key)
                commit_data = await self.git_manager.generate_conventional_commit(
                    diff_text, client, model
                )

                # Afficher les informations détaillées
                self._tui_output.add_message(f"Type: {commit_data.get('type', 'chore')}")
                if commit_data.get('scope'):
                    self._tui_output.add_message(f"Scope: {commit_data.get('scope')}")
                self._tui_output.add_message(f"Description: {commit_data.get('description', '')}")
                if commit_data.get('body'):
                    self._tui_output.add_message(f"Corps: {commit_data.get('body')}")
                if commit_data.get('breaking_change'):
                    self._tui_output.add_message(f"BREAKING CHANGE: {commit_data.get('breaking_change')}")

                # Afficher le message formaté
                commit_message = commit_data.get('formatted', '')
                self._tui_output.add_message(f"Message formaté: {commit_message}")
                
                # Demander confirmation
                self._tui_output.add_message("Confirmez-vous la création du commit? (o/n)")
                self._tui_state = "confirm_commit"
                self._tui_commit_message = commit_message

            elif task_type == "git_branch":
                # Traiter la tâche de suggestion de nom de branche
                description = self.tui_task_queue.get("description", "")
                model = self.tui_task_queue.get("model", "")

                client = AnthropicClient(api_key)
                branch_name = await self.git_manager.suggest_branch_name_with_claude(
                    description, client, model
                )

                self._tui_output.add_message(f"Nom de branche suggéré: {branch_name}")
                
                # Demander confirmation
                self._tui_output.add_message("Confirmez-vous la création de la branche? (o/n)")
                self._tui_state = "confirm_branch"
                self._tui_branch_name = branch_name

        except Exception as e:
            self._tui_output.add_message(f"Erreur lors du traitement de la tâche: {str(e)}")

        # Réinitialiser la tâche
        self.tui_task_queue = None

