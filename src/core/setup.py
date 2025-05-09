import argparse
import os
import sys
import textwrap

from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from src.core.modules.code_analysis import ProjectAnalyzer
from src.config.config import AylaConfig
from src.core.ui import UI


class AylaSetupAssistant:
    """Assistant de configuration pour Ayla CLI"""

    def __init__(self, config: AylaConfig, ui: UI):
        """Initialise l'assistant de configuration"""
        self.config = config
        self.ui = ui

    def _configure_parameters(self):
        """Configure les paramètres par défaut"""
        self.ui.console.print("\n[bold]3. Configuration des paramètres par défaut[/bold]")

        # Max tokens
        current_max_tokens = self.config.get_max_tokens()
        self.ui.console.print(f"Nombre maximum de tokens par défaut: [cyan]{current_max_tokens}[/cyan]")
        change_max_tokens = self.ui.get_input("Souhaitez-vous modifier cette valeur? (o/n): ").lower()
        if change_max_tokens in ('o', 'oui'):
            while True:
                try:
                    new_max_tokens = int(self.ui.get_input("Entrez la nouvelle valeur (1000-100000): "))
                    if 1000 <= new_max_tokens <= 100000:
                        self.config.set("default_max_tokens", new_max_tokens)
                        self.ui.print_info(f"Nombre maximum de tokens changé pour: {new_max_tokens}")
                        break
                    else:
                        self.ui.print_error("La valeur doit être entre 1000 et 100000.")
                except ValueError:
                    self.ui.print_error("Veuillez entrer un nombre valide.")

        # Température
        current_temp = self.config.get_temperature()
        self.ui.console.print(f"Température par défaut: [cyan]{current_temp}[/cyan]")
        change_temp = self.ui.get_input("Souhaitez-vous modifier cette valeur? (o/n): ").lower()
        if change_temp in ('o', 'oui'):
            while True:
                try:
                    new_temp = float(self.ui.get_input("Entrez la nouvelle valeur (0.0-1.0): "))
                    if 0.0 <= new_temp <= 1.0:
                        self.config.set("default_temperature", new_temp)
                        self.ui.print_info(f"Température changée pour: {new_temp}")
                        break
                    else:
                        self.ui.print_error("La valeur doit être entre 0.0 et 1.0.")
                except ValueError:
                    self.ui.print_error("Veuillez entrer un nombre valide.")

        # Streaming par défaut
        current_stream = self.config.get_stream()
        self.ui.console.print(f"Streaming par défaut: [cyan]{'Activé' if current_stream else 'Désactivé'}[/cyan]")
        change_stream = self.ui.get_input("Souhaitez-vous modifier ce paramètre? (o/n): ").lower()
        if change_stream in ('o', 'oui'):
            new_stream = self.ui.get_input("Activer le streaming par défaut? (o/n): ").lower() in ('o', 'oui')
            self.config.set("default_stream", new_stream)
            self.ui.print_info(f"Streaming par défaut {'activé' if new_stream else 'désactivé'}.")

    def _setup_alias(self):
        """Configure un alias pour l'application"""
        create_alias = self.ui.get_input("\nSouhaitez-vous créer un alias 'Ayla' pour ce script? (o/n): ").lower()
        if create_alias in ('o', 'oui'):
            script_path = os.path.abspath(sys.argv[0])
            bashrc_path = os.path.expanduser("~/.bashrc")

            alias_line = f'alias ayla="{script_path}"'

            # Vérifier si l'alias existe déjà
            try:
                with open(bashrc_path, 'r') as f:
                    if any(line.strip() == alias_line for line in f):
                        self.ui.print_info("L'alias 'ayla' existe déjà dans votre .bashrc")
                        return
            except FileNotFoundError:
                pass

            try:
                with open(bashrc_path, 'a') as f:
                    f.write(f"\n# Alias pour Ayla CLI\n{alias_line}\n")
                self.ui.print_info("Alias 'ayla' ajouté à votre .bashrc")
                self.ui.print_warning("N'oubliez pas d'exécuter 'source ~/.bashrc' pour activer l'alias.")
            except Exception as e:
                self.ui.print_error(f"Erreur lors de l'ajout de l'alias: {str(e)}")
                self.ui.print_info("Vous pouvez ajouter manuellement l'alias suivant à votre .bashrc:")
                self.ui.console.print(f"[code]{alias_line}[/code]")

    def _setup_project_analyzer_config(self):
        """Configure les options d'analyse de projet"""
        self.ui.console.print("\n[bold]Configuration de l'analyseur de projet[/bold]")

        config_data = self.config.load_config()

        # Afficher les exclusions actuelles
        excluded_dirs = config_data.get("excluded_dirs", ProjectAnalyzer.DEFAULT_EXCLUDED_DIRS)
        excluded_files = config_data.get("excluded_files", ProjectAnalyzer.DEFAULT_EXCLUDED_FILES)

        self.ui.console.print(f"Répertoires exclus actuels: [cyan]{', '.join(excluded_dirs)}[/cyan]")
        self.ui.console.print(f"Fichiers exclus actuels: [cyan]{', '.join(excluded_files)}[/cyan]")

        # Demander si l'utilisateur souhaite modifier les exclusions
        if Confirm.ask("Souhaitez-vous modifier les répertoires exclus?"):
            new_dirs = Prompt.ask(
                "Entrez les répertoires à exclure (séparés par des virgules)",
                default=", ".join(excluded_dirs)
            )
            excluded_dirs = [d.strip() for d in new_dirs.split(',')]
            self.config.set("excluded_dirs", excluded_dirs)

        if Confirm.ask("Souhaitez-vous modifier les fichiers exclus?"):
            new_files = Prompt.ask(
                "Entrez les fichiers à exclure (séparés par des virgules)",
                default=", ".join(excluded_files)
            )
            excluded_files = [f.strip() for f in new_files.split(',')]
            self.config.set("excluded_files", excluded_files)

        self.ui.console.print("[success]Configuration de l'analyseur de projet sauvegardée.[/success]")

    async def setup(self):
        """Lance l'assistant de configuration"""
        self.ui.console.print(Panel.fit(
            "[bold]Assistant de configuration Ayla CLI[/bold]\n\n"
            "Cet assistant va vous aider à configurer l'outil pour une utilisation optimale.",
            title="Configuration",
            border_style="blue"
        ))

        # Configuration de la clé API
        self.ui.console.print("\n[bold]1. Configuration de la clé API[/bold]")
        if self.config.get("api_key"):
            show_key = self.ui.get_input("Une clé API est déjà configurée. Souhaitez-vous la modifier? (o/n): ").lower()
            if show_key in ('o', 'oui'):
                api_key = self.ui.get_input("[bold]Veuillez entrer votre nouvelle clé API Anthropic: [/bold]")
                if api_key:
                    self.config.set("api_key", api_key)
                    self.ui.print_info("Nouvelle clé API sauvegardée.")
        else:
            api_key = self.ui.get_input("[bold]Veuillez entrer votre clé API Anthropic: [/bold]")
            if api_key:
                self.config.set("api_key", api_key)
                self.ui.print_info("Clé API sauvegardée.")

        # Configuration du modèle par défaut
        self.ui.console.print("\n[bold]2. Configuration du modèle par défaut[/bold]")
        self.ui.show_models_info(self.config.AVAILABLE_MODELS)

        current_model = self.config.get_model()
        self.ui.console.print(f"Modèle actuel: [cyan]{current_model}[/cyan]")

        change_model = self.ui.get_input("Souhaitez-vous changer le modèle par défaut? (o/n): ").lower()
        if change_model in ('o', 'oui'):
            model_options = list(self.config.AVAILABLE_MODELS.keys())
            for i, model in enumerate(model_options):
                description = self.config.AVAILABLE_MODELS[model]
                self.ui.console.print(f"[cyan]{i + 1}.[/cyan] {model} - {description}")

            while True:
                choice = self.ui.get_input("\nEntrez le numéro du modèle choisi (ou q pour annuler): ")
                if choice.lower() == 'q':
                    break

                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(model_options):
                        selected_model = model_options[choice_idx]
                        self.config.set("default_model", selected_model)
                        self.ui.print_info(f"Modèle par défaut changé pour: {selected_model}")
                        break
                    else:
                        self.ui.print_error("Numéro invalide. Veuillez réessayer.")
                except ValueError:
                    self.ui.print_error("Veuillez entrer un numéro valide.")

        # Configuration des paramètres par défaut
        self._configure_parameters()
        self._setup_project_analyzer_config()

        # Sauvegarder la configuration
        self.config.save_config()
        self.ui.console.print("\n[bold green]Configuration terminée et sauvegardée avec succès![/bold green]")

        # Demander si l'utilisateur souhaite créer un alias
        # self._setup_alias()

    @staticmethod
    def setup_argparse(config):
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
            default=config.DEFAULT_MODEL,
            help="Modèle à utiliser"
        )
        api_group.add_argument(
            "--max-tokens", "-t",
            type=int,
            default=config.DEFAULT_MAX_TOKENS,
            help="Nombre maximum de tokens"
        )
        api_group.add_argument(
            "--temperature", "-T",
            type=float,
            default=config.DEFAULT_TEMPERATURE,
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
            "--analysis-crew",
            choices=['research', 'code_review', 'code_analysis', 'analysis'],
            default=None,
            help="Analyse avancer avec des agents"
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
            default="stats",
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

