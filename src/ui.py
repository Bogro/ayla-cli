import curses
import sys
import threading
import time
from typing import Dict, Tuple, List

import os
import re
import math

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.theme import Theme
from rich.prompt import Prompt
from rich.live import Live
from rich.columns import Columns
from rich.table import Table


class UI:
    """Gestion de l'interface utilisateur"""

    def __init__(self):
        """Initialise l'interface utilisateur"""
        # Configuration des couleurs pour Rich
        custom_theme = Theme({
            "user": "bold cyan",
            "assistant": "bold green",
            "error": "bold red",
            "warning": "yellow",
            "info": "blue",
            "success": "green",
        })

        self.console = Console(theme=custom_theme)

    def print_success(self, message: str):
        """Affiche un message d'erreur"""
        self.console.print(f"[success]{message}[/success]")

    def print_error(self, message: str):
        """Affiche un message d'erreur"""
        self.console.print(f"[error]{message}[/error]")

    def print_warning(self, message: str):
        """Affiche un message d'avertissement"""
        self.console.print(f"[warning]{message}[/warning]")

    def print_info(self, message: str):
        """Affiche un message d'information"""
        self.console.print(f"[info]{message}[/info]")

    def print_user(self, message: str):
        """Affiche un message de l'utilisateur"""
        self.console.print(f"\n[user]Vous:[/user] {message}\n")

    def get_input(self, prompt: str = "") -> str:
        """Demande une entrée à l'utilisateur"""
        return self.console.input(prompt)

    def get_api_key_input(self) -> Tuple[str, bool]:
        """Demande la clé API à l'utilisateur et s'il souhaite la sauvegarder"""
        self.print_info("Aucune clé API Anthropic trouvée.")
        api_key = self.get_input("[bold]Veuillez entrer votre clé API Anthropic: [/bold]")

        if not api_key:
            self.print_error("Aucune clé API fournie. Impossible de continuer.")
            sys.exit(1)

        # Demander si l'utilisateur souhaite sauvegarder la clé
        save_key = self.get_input(
            "[bold]Voulez-vous sauvegarder cette clé pour une utilisation future? (o/n): [/bold]").lower()

        return api_key, save_key in ('o', 'oui')

    def format_code_blocks(self, text: str) -> List:
        """Détecte et formate les blocs de code dans le texte"""
        lines = text.split('\n')
        in_code_block = False
        code_block_lines = []
        language = ""
        formatted_parts = []
        current_text = []

        for line in lines:
            # Détection du début d'un bloc de code
            if line.startswith("```") and not in_code_block:
                # Ajouter le texte précédent s'il y en a
                if current_text:
                    formatted_parts.append("\n".join(current_text))
                    current_text = []

                in_code_block = True
                language = line[3:].strip()  # Extraire le langage de programmation
                continue

            # Détection de la fin d'un bloc de code
            elif line.startswith("```") and in_code_block:
                in_code_block = False
                # Créer un bloc de syntaxe colorée et l'ajouter aux parties formatées
                code = "\n".join(code_block_lines)
                syntax = Syntax(code, language or "text", theme="monokai", line_numbers=True)
                formatted_parts.append(syntax)
                code_block_lines = []
                continue

            # À l'intérieur d'un bloc de code
            if in_code_block:
                code_block_lines.append(line)
            else:
                current_text.append(line)

        # Ajouter le texte restant s'il y en a
        if current_text:
            formatted_parts.append("\n".join(current_text))

        return formatted_parts

    def print_assistant_response(self, response: str, raw: bool = False):
        """Affiche la réponse de l'assistant avec formatage"""
        if raw:
            print(response)
            return

        # Formater et afficher avec Rich
        formatted_parts = self.format_code_blocks(response)

        self.console.print("\n[assistant]Ayla:[/assistant]")
        for part in formatted_parts:
            if isinstance(part, str):
                # Traiter le texte normal comme du markdown
                md = Markdown(part)
                self.console.print(md)
            else:
                # C'est déjà un objet Rich (bloc de code)
                self.console.print(part)
        self.console.print()

    def display_conversation_history(self, history: List[Dict[str, str]]):
        """Affiche l'historique d'une conversation"""
        if not history:
            self.print_info("Cette conversation ne contient aucun message.")
            return

        for i, message in enumerate(history):
            role = message["role"]
            content = message["content"]

            if role == "user":
                self.console.print(f"\n[user]Vous ({i + 1}):[/user]")
                self.console.print(content)
            else:
                self.console.print(f"\n[assistant]Ayla ({i + 1}):[/assistant]")
                formatted_parts = self.format_code_blocks(content)
                for part in formatted_parts:
                    if isinstance(part, str):
                        md = Markdown(part)
                        self.console.print(md)
                    else:
                        self.console.print(part)

        self.console.print()

    def show_conversations_list(self, conversations: List[Dict]):
        """Affiche la liste des conversations sauvegardées"""
        if not conversations:
            self.print_info("Aucune conversation sauvegardée.")
            return

        self.console.print("\n[bold]Conversations sauvegardées:[/bold]")
        for i, conv in enumerate(conversations):
            self.console.print(f"[cyan]{i + 1}.[/cyan] [bold]{conv['id']}[/bold] - {conv['title']}")
            self.console.print(
                f"   [italic]{conv['messages']} messages | Dernière modification: {conv['last_modified']}[/italic]")

        self.console.print()

    def show_models_info(self, models: Dict[str, str]):
        """Affiche la liste des modèles disponibles"""
        self.console.print("\n[bold]Modèles Ayla disponibles:[/bold]")
        for model, description in models.items():
            self.console.print(f"[cyan]{model}[/cyan]: {description}")
        self.console.print()

    def show_interactive_help(self):
        """Affiche l'aide pour le mode interactif"""
        help_text = """
        [bold]Commandes disponibles en mode interactif:[/bold]

        /help, /?    : Affiche cette aide
        /exit, /quit, /q : Quitte le mode interactif
        /history     : Affiche l'historique de la conversation actuelle
        /clear       : Efface l'historique de la conversation actuelle
        /save [id]   : Sauvegarde la conversation avec un nouvel ID
        /list        : Liste toutes les conversations sauvegardées
        /load [id]   : Charge une conversation existante

        [italic]Appuyez sur Ctrl+C pour quitter à tout moment.[/italic]
        """
        self.console.print(Panel(help_text, title="Aide", border_style="blue"))

    def create_progress(self, message: str = "Ayla réfléchit...", transient: bool = True):
        """Crée une barre de progression"""
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[info]{message}[/info]"),
            transient=transient,
        )
        return progress

    def display_conventional_commit(self, commit_data: Dict[str, str]) -> None:
        """Affiche un message de commit conventionnel avec une mise en forme"""
        # Afficher le résumé
        self.console.print("\n[bold]Message de commit conventionnel[/bold]")
        
        # Afficher le type avec une couleur spécifique
        commit_type = commit_data.get('type', 'chore')
        type_color = {
            'feat': 'green',
            'fix': 'red',
            'docs': 'blue',
            'style': 'magenta',
            'refactor': 'cyan',
            'perf': 'yellow',
            'test': 'green3',
            'build': 'white',
            'ci': 'white',
            'chore': 'dim white'
        }.get(commit_type, 'white')
        
        self.console.print(f"\n[bold cyan]Type:[/bold cyan] [{type_color}]{commit_type}[/{type_color}]")
        
        # Afficher le scope s'il existe
        if 'scope' in commit_data and commit_data['scope']:
            self.console.print(f"[bold cyan]Scope:[/bold cyan] {commit_data['scope']}")
            
        # Afficher la description
        description = commit_data.get('description', 'Mise à jour du code')
        self.console.print(f"[bold cyan]Description:[/bold cyan] {description}")
        
        # Afficher le corps s'il existe
        if 'body' in commit_data and commit_data['body']:
            self.console.print("\n[bold cyan]Corps:[/bold cyan]")
            self.console.print(commit_data['body'])
            
        # Afficher les breaking changes s'ils existent
        if 'breaking_change' in commit_data and commit_data['breaking_change']:
            self.console.print("\n[bold red]BREAKING CHANGE:[/bold red]")
            self.console.print(commit_data['breaking_change'])
            
        # Afficher le message formaté
        if 'formatted' in commit_data and commit_data['formatted']:
            self.console.print("\n[bold green]Message formaté:[/bold green]")
            self.console.print(f"[bold]{commit_data['formatted']}[/bold]")
            
        self.console.print()


class TUIManager:
    """Gestionnaire d'interface utilisateur texte avancée (TUI)"""

    def __init__(self, app_context=None):
        """
        Initialise le gestionnaire de TUI

        Args :
            app_context : Référence à l'application principale pour accéder aux fonctionnalités
        """
        self.app_context = app_context
        self.screen = None
        self.max_y = 0
        self.max_x = 0

        # Zones d'affichage
        self.command_window = None
        self.output_window = None
        self.help_window = None
        self.status_window = None

        # État de l'interface
        self.current_command = ""
        self.cursor_position = 0
        self.command_history = []
        self.history_position = 0
        self.running = False
        self.show_help = True

        # Auto-complétion
        self.available_commands = {
            "/help": "Affiche l'aide générale",
            "/quit": "Quitte le mode TUI",
            "/clear": "Efface l'historique de l'écran",
            "/analyze": "Analyse un fichier de code - /analyze <fichier> [type]",
            "/document": "Génère de la documentation - /document <fichier> [type]",
            "/history": "Affiche l'historique des conversations",
            "/save": "Sauvegarde la conversation - /save [id]",
            "/load": "Charge une conversation - /load <id>",
            "/list": "Liste les conversations enregistrées",
            "/search": "Recherche dans les conversations - /search <terme>",
            "/template": "Utilise un template - /template <nom>",
            "/models": "Liste les modèles disponibles",
            "/git-status": "Affiche le statut du dépôt Git actuel",
            "/git-commit": "Génère un message de commit intelligent pour les changements",
            "/git-branch": "Suggère un nom de branche intelligent - /git-branch <description>",
            "/git-analyze": "Analyse le dépôt Git et fournit des insights",
            "/git-diff": "Analyse détaillée des changements actuels avec Claude",
            "/git-conventional": "Génère un message de commit au format Conventional Commits",
        }

        # Aide contextuelle pour les commandes (arguments et sous-commandes)
        self.command_help = {
            "/analyze": {
                "args": ["<fichier>", "[type]"],
                "types": ["general", "security", "performance", "style"],
                "help": "Analyse un fichier de code avec différentes perspectives"
            },
            "/document": {
                "args": ["<fichier>", "[type]"],
                "types": ["complete", "api", "usage"],
                "help": "Génère de la documentation pour un fichier de code"
            },
            "/save": {
                "args": ["[id]"],
                "help": "Sauvegarde la conversation actuelle avec un ID optionnel"
            },
            "/load": {
                "args": ["<id>"],
                "help": "Charge une conversation existante par son ID"
            },
            "/search": {
                "args": ["<terme>"],
                "help": "Recherche un terme dans toutes les conversations"
            },
            "/template": {
                "args": ["<nom>"],
                "help": "Utilise un template préenregistré"
            }
        }

        # Aide pour les commandes Git
        self.git_commands_help = {
            "/git-status": {
                "help": "Affiche le statut du dépôt Git actuel"
            },
            "/git-commit": {
                "help": "Génère un message de commit intelligent basé sur les changements actuels"
            },
            "/git-branch": {
                "args": ["<description>"],
                "help": "Suggère un nom de branche intelligent basé sur la description fournie"
            },
            "/git-analyze": {
                "help": "Analyse le dépôt Git et fournit des insights sur son état et son histoire"
            },
            "/git-diff": {
                "help": "Analyse détaillée des changements actuels avec Claude"
            },
            "/git-conventional": {
                "help": "Génère un message de commit au format Conventional Commits"
            },
            "/git-push": {
                "args": ["[remote]", "[branche]"],
                "help": "Pousse les changements vers le dépôt distant"
            },
            "/git-pull": {
                "args": ["[remote]", "[branche]"],
                "help": "Tire les changements depuis le dépôt distant"
            }
        }
        
        # Ajouter les commandes Git à l'aide générale
        self.command_help.update(self.git_commands_help)

    def start(self):
        """Démarre l'interface TUI"""
        # Lancer curses dans un wrapper qui gère le nettoyage
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        """Boucle principale de l'interface"""
        # Initialiser l'écran
        self.screen = stdscr
        self.running = True
        curses.curs_set(1)  # Afficher le curseur
        curses.use_default_colors()

        if curses.has_colors():
            self._init_colors()

        # Configurer les zones de l'interface
        self._setup_windows()

        # Boucle principale
        while self.running:
            # Mesurer la taille de l'écran pour détecter les redimensionnements
            new_y, new_x = self.screen.getmaxyx()
            if new_y != self.max_y or new_x != self.max_x:
                self.max_y, self.max_x = new_y, new_x
                self._setup_windows()

            # Afficher les composants
            self._draw_interface()

            # Traiter l'entrée utilisateur
            self._process_input()

    def _init_colors(self):
        """Initialise les paires de couleurs"""
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # Commandes
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # Messages utilisateur
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Messages système
        curses.init_pair(4, curses.COLOR_RED, -1)  # Erreurs
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Barre de statut
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Zone d'aide

    def _setup_windows(self):
        """Configure les fenêtres de l'interface"""
        self.max_y, self.max_x = self.screen.getmaxyx()

        # Zone de sortie (occupe la plupart de l'écran)
        output_height = self.max_y - 6  # Réserve des lignes pour commande et aide/statut
        self.output_window = curses.newwin(output_height, self.max_x, 0, 0)

        # Zone d'aide contextuelle (3 lignes au-dessus de la zone de commande)
        self.help_window = curses.newwin(3, self.max_x, output_height, 0)

        # Zone de commande (1 ligne en bas de l'écran - 1)
        self.command_window = curses.newwin(1, self.max_x, self.max_y - 2, 0)

        # Barre de statut (tout en bas)
        self.status_window = curses.newwin(1, self.max_x, self.max_y - 1, 0)

    def _draw_interface(self):
        """Dessine l'interface complète"""
        self._draw_status_bar()
        self._draw_command_line()
        self._draw_help()
        self.screen.refresh()

    def _draw_status_bar(self):
        """Dessine la barre de statut"""
        self.status_window.clear()
        self.status_window.bkgd(' ', curses.color_pair(5))
        status_text = " TUI Mode | Appuyez sur Ctrl+H pour afficher/masquer l'aide | Ctrl+C pour quitter"
        self.status_window.addstr(0, 0, status_text)
        self.status_window.refresh()

    def _draw_command_line(self):
        """Dessine la ligne de commande"""
        self.command_window.clear()
        prompt = "> "
        self.command_window.addstr(0, 0, prompt)
        self.command_window.addstr(0, len(prompt), self.current_command)
        self.command_window.move(0, len(prompt) + self.cursor_position)
        self.command_window.refresh()

    def _draw_help(self):
        """Dessine la zone d'aide contextuelle"""
        if not self.show_help:
            self.help_window.clear()
            self.help_window.refresh()
            return

        self.help_window.clear()
        self.help_window.bkgd(' ', curses.color_pair(6))

        # Déterminer l'aide à afficher en fonction de la commande actuelle
        help_text = []
        current_input = self.current_command.strip()

        if not current_input:
            # Aide générale quand aucune commande n'est saisie
            help_text.append("Tapez une commande ou une question")
            help_text.append("Commandes disponibles: " + ", ".join(sorted(self.available_commands.keys())))
        elif current_input.startswith('/'):
            # Identifier la commande et afficher l'aide appropriée
            parts = current_input.split()
            command = parts[0]

            # Autocomplétion des commandes
            matching_commands = [cmd for cmd in self.available_commands.keys() if cmd.startswith(command)]

            if len(matching_commands) == 1 and matching_commands[0] in self.command_help:
                # Aide détaillée pour une commande spécifique
                cmd_help = self.command_help[matching_commands[0]]
                help_text.append(f"{matching_commands[0]} {' '.join(cmd_help['args'])}")
                help_text.append(cmd_help['help'])

                # Suggestions d'autocomplétion pour les sous-commandes
                if len(parts) > 1 and 'types' in cmd_help:
                    arg_prefix = parts[-1].lower()
                    suggestions = [t for t in cmd_help['types'] if t.startswith(arg_prefix)]
                    if suggestions:
                        help_text.append("Options: " + ", ".join(suggestions))
            elif matching_commands:
                # Suggestions de commandes pour autocomplétion
                help_text.append("Commandes correspondantes:")
                for cmd in matching_commands:
                    help_text.append(f"  {cmd} - {self.available_commands[cmd]}")
            else:
                help_text.append("Commande inconnue")
        else:
            # Aide pour le mode question
            help_text.append("Mode question: votre message sera envoyé à Claude")
            help_text.append("Utilisez / pour entrer une commande")

        # Afficher l'aide limitée à la hauteur de la fenêtre
        for i, line in enumerate(help_text[:3]):  # Limité à 3 lignes
            self.help_window.addstr(i, 1, line)

        self.help_window.refresh()

    def _process_input(self):
        """Traite l'entrée utilisateur"""
        try:
            key = self.command_window.getch()

            if key == curses.KEY_RESIZE:
                # Le redimensionnement est détecté dans la boucle principale
                pass
            elif key == ord('\n'):  # Entrée
                self._execute_command()
            elif key == curses.KEY_BACKSPACE or key == 127:  # Retour arrière
                if self.cursor_position > 0:
                    self.current_command = (self.current_command[:self.cursor_position - 1] +
                                            self.current_command[self.cursor_position:])
                    self.cursor_position -= 1
            elif key == curses.KEY_DC:  # Supprimer
                if self.cursor_position < len(self.current_command):
                    self.current_command = (self.current_command[:self.cursor_position] +
                                            self.current_command[self.cursor_position + 1:])
            elif key == curses.KEY_LEFT:  # Flèche gauche
                if self.cursor_position > 0:
                    self.cursor_position -= 1
            elif key == curses.KEY_RIGHT:  # Flèche droite
                if self.cursor_position < len(self.current_command):
                    self.cursor_position += 1
            elif key == curses.KEY_UP:  # Flèche haut (historique)
                self._navigate_history(-1)
            elif key == curses.KEY_DOWN:  # Flèche bas (historique)
                self._navigate_history(1)
            elif key == 9:  # Tab (autocomplétion)
                self._autocomplete()
            elif key == curses.KEY_HOME:  # Début de ligne
                self.cursor_position = 0
            elif key == curses.KEY_END:  # Fin de ligne
                self.cursor_position = len(self.current_command)
            elif key == 8:  # Ctrl+H (afficher/masquer l'aide)
                self.show_help = not self.show_help
            elif key == 3:  # Ctrl+C (quitter)
                self.running = False
            elif 32 <= key <= 126:  # Caractères imprimables
                self.current_command = (self.current_command[:self.cursor_position] +
                                        chr(key) +
                                        self.current_command[self.cursor_position:])
                self.cursor_position += 1

        except Exception as e:
            self._add_to_output(f"Erreur: {str(e)}", color=4)

    def _navigate_history(self, direction):
        """
        Navigue dans l'historique des commandes

        Args:
            direction: -1 pour remonter, 1 pour descendre
        """
        if not self.command_history:
            return

        new_position = self.history_position + direction

        if 0 <= new_position < len(self.command_history):
            self.history_position = new_position
            self.current_command = self.command_history[self.history_position]
            self.cursor_position = len(self.current_command)
        elif new_position == len(self.command_history):
            # Après la dernière entrée de l'historique, revenir à une entrée vide
            self.history_position = new_position
            self.current_command = ""
            self.cursor_position = 0

    def _autocomplete(self):
        """Gère l'autocomplétion des commandes et arguments"""
        if not self.current_command:
            return

        parts = self.current_command.split()

        # Autocomplétion de commande
        if len(parts) == 1 and parts[0].startswith('/'):
            matching_commands = [cmd for cmd in self.available_commands.keys()
                                 if cmd.startswith(parts[0])]

            if len(matching_commands) == 1:
                # Une seule commande correspond, on la complète
                self.current_command = matching_commands[0] + " "
                self.cursor_position = len(self.current_command)

        # Autocomplétion d'arguments
        elif len(parts) > 1 and parts[0] in self.command_help:
            cmd_help = self.command_help[parts[0]]

            # Si la commande a des options/types
            if 'types' in cmd_help:
                current_arg = parts[-1]
                matching_options = [opt for opt in cmd_help['types']
                                    if opt.startswith(current_arg)]

                if len(matching_options) == 1:
                    # Remplacer l'argument actuel par l'option complète
                    self.current_command = ' '.join(parts[:-1]) + ' ' + matching_options[0] + ' '
                    self.cursor_position = len(self.current_command)

    def _execute_command(self):
        """Exécute la commande saisie"""
        command = self.current_command.strip()

        if not command:
            return

        # Ajouter la commande à l'historique
        self.command_history.append(command)
        self.history_position = len(self.command_history)

        # Afficher la commande dans la sortie
        self._add_to_output(f"> {command}", color=2)

        # Traiter la commande
        if command.startswith('/'):
            self._process_command(command)
        else:
            self._process_question(command)

        # Réinitialiser la ligne de commande
        self.current_command = ""
        self.cursor_position = 0

    def _process_command(self, command):
        """Traite une commande slash"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        try:
            if cmd == '/quit':
                self.running = False
            elif cmd == '/clear':
                self.output_window.clear()
                self.output_window.refresh()
            elif cmd == '/help':
                self._show_full_help()
            # Autres commandes seraient redirigées vers l'app_context
            else:
                if self.app_context:
                    # Vérifier que la méthode execute_tui_command existe
                    if not hasattr(self.app_context, 'execute_tui_command'):
                        self._add_to_output(f"Erreur: La méthode execute_tui_command n'est pas disponible.", color=4)
                        return

                    # Méthode qui devrait être implémentée dans votre application
                    # pour traiter les commandes TUI et retourner un résultat
                    result = self.app_context.execute_tui_command(cmd, args)
                    if result:
                        self._add_to_output(result)
                else:
                    self._add_to_output(f"Commande non implémentée: {cmd}", color=3)
        except Exception as e:
            # Gérer les erreurs de traitement des commandes
            error_message = f"Erreur lors de l'exécution de la commande {cmd}: {str(e)}"
            self._add_to_output(error_message, color=4)

            # Journaliser l'erreur pour le débogage
            import traceback
            trace = traceback.format_exc()
            try:
                with open("tui_command_error.log", "a") as f:
                    import time
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Command: {command}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(trace + "\n")
            except Exception:
                pass

    def _process_question(self, question):
        """Traite une question à envoyer à Claude"""
        self._add_to_output("Envoi de votre message à Claude...", color=3)

        # Simuler une réponse asynchrone
        if self.app_context:
            # Lancer le traitement dans un thread pour ne pas bloquer l'interface
            thread = threading.Thread(
                target=self._async_question_handler,
                args=(question,)
            )
            thread.daemon = True
            thread.start()
        else:
            self._add_to_output("Mode simulation: Pas de connexion à Claude", color=3)
            self._add_to_output("Voici une réponse simulée pour votre question.", color=1)

    def _async_question_handler(self, question):
        """Gère l'envoi asynchrone de la question à Claude"""
        try:
            # Afficher un message d'attente
            self._add_to_output("Envoi de votre question à Claude...", color=3)
            self._add_to_output("En attente de réponse...", color=3)

            # Vérifier que app_context existe
            if not self.app_context:
                self._add_to_output("Erreur: Application non initialisée correctement.", color=4)
                return

            # Vérifier que la méthode send_question_to_claude existe
            if not hasattr(self.app_context, 'send_question_to_claude'):
                self._add_to_output("Erreur: Méthode d'envoi de question non disponible.", color=4)
                return

            # Utiliser asyncio pour exécuter la méthode asynchrone
            import asyncio

            # Créer une nouvelle boucle d'événements pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Exécuter la requête asynchrone
            response = loop.run_until_complete(
                self.app_context.send_question_to_claude(question)
            )

            # Fermer la boucle
            loop.close()

            # Si la réponse contient un message d'erreur, l'afficher en rouge
            if response and response.startswith("Erreur lors de l'envoi"):
                self._add_to_output(response, color=4)
                self._add_to_output("Consultez le fichier claude_error.log pour plus de détails.", color=3)
                return

            # Si la réponse est trop longue, découper en parties pour l'affichage
            if len(response) > 2000:
                # Découper la réponse en parties de 1000 caractères maximum
                parts = [response[i:i+1000] for i in range(0, len(response), 1000)]

                # Afficher un message d'information
                self._add_to_output("Réponse longue - affichage par parties:", color=3)

                # Afficher chaque partie avec un délai pour permettre le défilement
                for i, part in enumerate(parts):
                    self._add_to_output(f"Partie {i+1}/{len(parts)}:", color=1)
                    self._add_to_output(part)

                    # Pause pour laisser l'utilisateur lire (sauf dernière partie)
                    if i < len(parts) - 1:
                        time.sleep(0.5)
            else:
                # Réponse assez courte, l'afficher directement
                self._add_to_output("Réponse de Claude:", color=1)
                self._add_to_output(response)

            # Force refresh de l'interface
            self.screen.noutrefresh()
            curses.doupdate()

        except asyncio.CancelledError:
            self._add_to_output("Requête annulée.", color=3)

        except Exception as e:
            # En cas d'erreur, l'afficher
            error_message = f"Erreur lors de la communication avec Claude: {str(e)}"
            self._add_to_output(error_message, color=4)

            # Fournir des informations supplémentaires selon le type d'erreur
            if "api_key" in str(e):
                self._add_to_output("→ Problème avec la clé API. Vérifiez votre configuration.", color=4)
            elif "connection" in str(e).lower():
                self._add_to_output("→ Problème de connexion. Vérifiez votre accès Internet.", color=4)
            elif "timeout" in str(e).lower():
                self._add_to_output("→ Délai d'attente dépassé. La requête a pris trop de temps.", color=4)

            # Log l'erreur complète si possible
            import traceback
            trace = traceback.format_exc()

            # Écrire dans un fichier log pour déboguer sans casser l'interface
            try:
                with open("tui_error.log", "a") as f:
                    f.write(f"\n--- Error at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"Question: {question}\n")
                    f.write(error_message + "\n")
                    f.write(trace + "\n")
                self._add_to_output("Plus de détails disponibles dans le fichier tui_error.log", color=3)
            except Exception:
                pass

    def _add_to_output(self, text, color=0):
        """
        Ajoute du texte à la fenêtre de sortie

        Args:
            text: Texte à ajouter
            color: Index de la paire de couleurs à utiliser
        """
        try:
            # Obtenir la position actuelle
            y, x = self.output_window.getyx()

            # Ajouter une nouvelle ligne si nécessaire
            if x > 0:
                self.output_window.addstr('\n')
                y += 1

            # Diviser le texte en lignes
            lines = text.split('\n')

            # Afficher chaque ligne avec gestion de l'overflowing
            for line in lines:
                # Calculer combien de lignes supplémentaires seront nécessaires
                width = self.max_x - 1
                extra_lines = len(line) // width

                # Faire défiler si nécessaire
                max_y = self.output_window.getmaxyx()[0] - 1
                if y + extra_lines > max_y:
                    self.output_window.scroll(y + extra_lines - max_y)
                    y = max_y - extra_lines

                # Ajouter le texte
                if curses.has_colors():
                    self.output_window.addstr(line, curses.color_pair(color))
                else:
                    self.output_window.addstr(line)

                # Mettre à jour la position Y
                y += extra_lines + 1

            self.output_window.refresh()
        except Exception as e:
            # En cas d'erreur, essayer de l'afficher sans plantage
            try:
                self.status_window.clear()
                self.status_window.addstr(0, 0, f"Erreur d'affichage: {str(e)}", curses.color_pair(4))
                self.status_window.refresh()
            except:
                pass

    def _show_full_help(self):
        """Affiche l'aide complète"""
        # Titre principal
        self._add_to_output("\n=== GUIDE D'UTILISATION DU MODE TUI ===", color=1)

        # Navigation et raccourcis
        self._add_to_output("\n[Navigation et raccourcis]", color=2)
        self._add_to_output("  Flèches gauche/droite : Déplacer le curseur")
        self._add_to_output("  Flèches haut/bas     : Parcourir l'historique des commandes")
        self._add_to_output("  Tab                  : Autocomplétation")
        self._add_to_output("  Ctrl+H               : Afficher/Masquer l'aide contextuelle")
        self._add_to_output("  Début/Fin            : Aller au début/fin de la ligne")
        self._add_to_output("  Suppr                : Supprimer le caractère sous le curseur")
        self._add_to_output("  Ctrl+C               : Quitter le mode TUI")

        # Commandes principales
        self._add_to_output("\n[Commandes principales]", color=2)
        for cmd, desc in sorted(self.available_commands.items()):
            self._add_to_output(f"  {cmd:<15} : {desc}")

        # Interactions avec Claude
        self._add_to_output("\n[Interagir avec Claude]", color=2)
        self._add_to_output("  1. Posez vos questions directement en les tapant (sans '/')")
        self._add_to_output("  2. Appuyez sur Entrée pour envoyer votre message à Claude")
        self._add_to_output("  3. Attendez la réponse (elle s'affichera automatiquement)")
        self._add_to_output("  4. Pour les réponses longues, elles seront affichées en plusieurs parties")

        # Exemples
        self._add_to_output("\n[Exemples d'utilisation]", color=2)
        self._add_to_output("  > Comment fonctionne la récursivité en Python?")
        self._add_to_output("     → Pose une question directe à Claude")
        self._add_to_output("  > /analyze main.py")
        self._add_to_output("     → Analyse le fichier main.py")
        self._add_to_output("  > /list")
        self._add_to_output("     → Affiche la liste des conversations")
        self._add_to_output("  > /load 20240530123456")
        self._add_to_output("     → Charge la conversation avec l'ID spécifié")

        # Conseils
        self._add_to_output("\n[Conseils]", color=2)
        self._add_to_output("  • Utilisez /save pour sauvegarder régulièrement votre conversation")
        self._add_to_output("  • Pour analyser du code, utilisez /analyze plutôt que de coller le code")
        self._add_to_output("  • Pour les réponses très longues, vous pouvez faire défiler avec Page Up/Down")
        self._add_to_output("  • Si l'interface ne répond plus, utilisez Ctrl+C pour sortir proprement")

        # Informations
        self._add_to_output("\n[À propos]", color=2)
        self._add_to_output("  Ayla CLI - Interface en ligne de commande pour Claude")
        self._add_to_output("  Version: 1.0.0")
        self._add_to_output("  Mode TUI: Interface utilisateur textuelle")

        # Aide finale
        self._add_to_output("\nTapez une commande ou une question pour continuer...", color=3)