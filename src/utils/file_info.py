import os
from typing import Dict, Any

# Dictionnaire de correspondance entre extensions et langages
LANGUAGE_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'jsx',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.sql': 'sql',
    '.sh': 'bash',
    '.bash': 'bash',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'sass',
    '.json': 'json',
    '.md': 'markdown',
    '.xml': 'xml',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.dart': 'dart',
    '.r': 'r',
    '.pl': 'perl',
    '.lua': 'lua',
    '.m': 'objective-c',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.erl': 'erlang',
    '.fs': 'fsharp',
    '.hs': 'haskell',
    '.clj': 'clojure',
}


class FileInfo:
    """Classe pour gérer et extraire des informations sur les fichiers de code"""

    def __init__(self, file_path: str):
        """
        Initialise l'objet FileInfo avec un chemin de fichier.

        Args:
            file_path: Chemin vers le fichier à analyser
        """
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.directory = os.path.dirname(file_path)
        self.extension = os.path.splitext(file_path)[1].lower()
        self.language = self._determine_language()
        self.content = None
        self.size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        self.line_count = 0
        self.stats = {}

    def _determine_language(self) -> str:
        """
        Détermine le langage de programmation basé sur l'extension du fichier.

        Returns :
            Le nom du langage ou 'text' si non reconnu
        """
        return LANGUAGE_EXTENSIONS.get(self.extension, 'text')

    def load_content(self) -> str:
        """
        Charge le contenu du fichier avec gestion d'encodage.

        Returns :
            Le contenu du fichier sous forme de texte

        Raises :
            FileNotFoundError : Si le fichier n'existe pas
            PermissionError : Si le fichier n'est pas accessible
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Le fichier {self.file_path} n'existe pas")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
        except UnicodeDecodeError:
            # Essayer avec une autre encodage
            try:
                with open(self.file_path, 'r', encoding='latin-1') as f:
                    self.content = f.read()
            except Exception as e:
                raise RuntimeError(f"Impossible de lire le fichier {self.file_path}: {str(e)}")

        # Calculer des statistiques basiques
        lines = self.content.split('\n')
        self.line_count = len(lines)
        self.stats = {
            'line_count': self.line_count,
            'char_count': len(self.content),
            'empty_lines': sum(1 for line in lines if line.strip() == '')
        }

        return self.content

    def get_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé des informations du fichier.

        Returns :
            Dictionnaire contenant les informations résumées
        """
        if self.content is None:
            try:
                self.load_content()
            except Exception as e:
                return {
                    'file_path': self.file_path,
                    'file_name': self.file_name,
                    'language': self.language,
                    'size': self.size,
                    'error': str(e)
                }

        return {
            'file_path': self.file_path,
            'file_name': self.file_name,
            'language': self.language,
            'extension': self.extension,
            'size': self.size,
            'line_count': self.line_count,
            'stats': self.stats
        }
