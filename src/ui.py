import sys
from typing import List, Dict, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.theme import Theme


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
        })

        self.console = Console(theme=custom_theme)

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
