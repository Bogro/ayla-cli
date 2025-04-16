from typing import Optional

from src.core.ui import UI


class FileManager:
    """Gestion des fichiers"""

    def __init__(self, ui: UI):
        """Initialise le gestionnaire de fichiers"""
        self.ui = ui

    def read_file_content(self, file_path: str) -> Optional[str]:
        """Lit le contenu d'un fichier"""
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            self.ui.print_error(f"Erreur lors de la lecture du fichier {file_path}: {str(e)}")
            return None
