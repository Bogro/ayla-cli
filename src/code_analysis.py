import os
import re
from typing import List, Dict, Any

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


class CodeAnalyzer:
    """Classe pour analyser du code et générer des prompts pour Claude"""

    def __init__(self, console=None):
        """
        Initialise l'analyseur de code.

        Args :
            console : Objet console pour l'affichage (optionnel)
        """
        self.console = console
        self.file_info = None

    def load_file(self, file_path: str) -> FileInfo:
        """
        Charge un fichier pour analyse.

        Args :
            file_path : Chemin vers le fichier à analyser

        Returns :
            Objet FileInfo contenant les informations du fichier
        """
        self.file_info = FileInfo(file_path)
        self.file_info.load_content()

        if self.console:
            self.console.print(
                f"[info]Fichier chargé: {file_path} ({self.file_info.language}, {self.file_info.line_count} lignes)[/info]")

        return self.file_info

    def generate_analysis_prompt(self, analysis_type: str = 'general') -> str:
        """
        Génère un prompt pour l'analyse de code.

        Args :
            analysis_type : Type d'analyse ('general', 'security', 'performance', 'style')

        Returns :
            Prompt formaté pour Claude
        """
        if not self.file_info or not self.file_info.content:
            raise ValueError("Aucun fichier chargé. Utilisez load_file() d'abord.")

        prompts = {
            'general': f"""Analyse ce code {self.file_info.language}. Inclus dans ta réponse :
1. Une explication de haut niveau de ce que fait le code
2. Les points forts et les bonnes pratiques utilisées
3. Les problèmes potentiels, bugs, ou failles de sécurité
4. Des suggestions d'amélioration spécifiques
5. Des exemples de refactorisation si nécessaire

Voici le code :
```{self.file_info.language}
{self.file_info.content}
```""",

            'security': f"""Réalise une analyse de sécurité complète pour ce code {self.file_info.language}. Identifie :
1. Toutes les vulnérabilités de sécurité potentielles
2. Les problèmes d'injection, XSS, CSRF ou autres attaques courantes
3. Les mauvaises pratiques de sécurité
4. Les risques liés à la gestion des données sensibles
5. Des recommandations pour corriger chaque problème identifié

Voici le code :
```{self.file_info.language}
{self.file_info.content}
```""",

            'performance': f"""Analyse les performances de ce code {self.file_info.language}. Identifie :
1. Les goulots d'étranglement potentiels
2. Les opérations inefficaces ou redondantes
3. Les problèmes d'utilisation mémoire
4. Les algorithmes ou structures de données qui pourraient être optimisés
5. Des suggestions concrètes d'optimisation avec exemples

Voici le code :
```{self.file_info.language}
{self.file_info.content}
```""",

            'style': f"""Vérifie le style et la qualité de ce code {self.file_info.language}. Inclus :
1. Évaluation de la lisibilité et maintenabilité
2. Respect des conventions de nommage et formatage
3. Cohérence du style dans tout le code
4. Suggestions pour améliorer la clarté
5. Réorganisation proposée pour une meilleure structure

Voici le code :
```{self.file_info.language}
{self.file_info.content}
```"""
        }

        return prompts.get(analysis_type, prompts['general'])

    def extract_functions_classes(self) -> Dict[str, List[str]]:
        """
        Extrait les fonctions et classes du code (analyse simple).

        Returns :
            Dictionnaire avec les listes de fonctions et classes
        """
        if not self.file_info or not self.file_info.content:
            raise ValueError("Aucun fichier chargé. Utilisez load_file() d'abord.")

        result = {
            'functions': [],
            'classes': []
        }

        # Extraction basique pour Python
        if self.file_info.language == 'python':
            # Regex pour les fonctions
            function_pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            functions = re.findall(function_pattern, self.file_info.content)
            result['functions'] = functions

            # Regex pour les classes
            class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            classes = re.findall(class_pattern, self.file_info.content)
            result['classes'] = classes

        # Extraction basique pour JavaScript
        elif self.file_info.language in ['javascript', 'typescript']:
            # Regex pour les fonctions
            function_pattern = r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            functions = re.findall(function_pattern, self.file_info.content)

            # Regex pour les fonctions flèche
            arrow_func_pattern = r'const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\([^)]*\)\s*=>'
            arrow_functions = re.findall(arrow_func_pattern, self.file_info.content)

            result['functions'] = functions + arrow_functions

            # Regex pour les classes
            class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            classes = re.findall(class_pattern, self.file_info.content)
            result['classes'] = classes

        return result


class DocumentationGenerator:
    """Classe pour générer de la documentation à partir de code"""

    def __init__(self, console=None):
        """
        Initialise le générateur de documentation.

        Args :
            console : Objet console pour l'affichage (optionnel)
        """
        self.console = console
        self.analyzer = CodeAnalyzer(console)
        self.file_info = None

    def load_file(self, file_path: str) -> FileInfo:
        """
        Charge un fichier pour la génération de documentation.

        Args :
            file_path : Chemin vers le fichier à documenter

        Returns :
            Objet FileInfo contenant les informations du fichier
        """
        self.file_info = self.analyzer.load_file(file_path)
        return self.file_info

    def generate_documentation_prompt(self, doc_format: str = 'markdown', doc_type: str = 'complete') -> str:
        """
        Génère un prompt pour la création de documentation.

        Args :
            doc_format : Format de la documentation ('markdown', 'html', 'rst')
            doc_type : Type de documentation ('complete', 'api', 'usage')

        Returns :
            Prompt formaté pour Claude
        """
        if not self.file_info or not self.file_info.content:
            raise ValueError("Aucun fichier chargé. Utilisez load_file() d'abord.")

        # Extraire les fonctions et classes pour une documentation plus ciblée
        code_elements = self.analyzer.extract_functions_classes()
        functions_str = ", ".join(code_elements['functions'])
        classes_str = ", ".join(code_elements['classes'])

        elements_summary = ""
        if functions_str or classes_str:
            elements_summary = "\n\nCe code semble contenir "
            if classes_str:
                elements_summary += f"les classes suivantes : {classes_str}"
            if functions_str:
                if classes_str:
                    elements_summary += f" et les fonctions suivantes : {functions_str}"
                else:
                    elements_summary += f"les fonctions suivantes : {functions_str}"
            elements_summary += ". Assure-toi de documenter ces éléments en détail."

        prompts = {
            'complete': f"""Génère une documentation complète pour ce code {self.file_info.language} au format {doc_format}.
La documentation doit inclure :
1. Une vue d'ensemble décrivant le but et la fonctionnalité du code
2. Une documentation détaillée pour chaque classe, méthode et fonction
3. Les paramètres, types et valeurs de retour pour chaque fonction
4. Des exemples d'utilisation pour les fonctionnalités principales
5. Les dépendances ou prérequis nécessaires{elements_summary}

Voici le code à documenter :
```{self.file_info.language}
{self.file_info.content}
```""",

            'api': f"""Génère une documentation d'API pour ce code {self.file_info.language} au format {doc_format}.
Concentre-toi uniquement sur l'interface publique :
1. Signature des fonctions/méthodes publiques avec leurs paramètres et types
2. Description claire de ce que fait chaque fonction/méthode
3. Valeurs de retour et exceptions possibles
4. Exemples d'appels pour chaque fonction/méthode
5. Contraintes ou limitations connues{elements_summary}

Voici le code à documenter :
```{self.file_info.language}
{self.file_info.content}
```""",

            'usage': f"""Crée un guide d'utilisation pour ce code {self.file_info.language} au format {doc_format}.
Le guide doit être orienté utilisateur et inclure :
1. Une introduction expliquant à quoi sert ce code
2. Des exemples pas-à-pas d'utilisation pour les cas d'usage courants
3. Des extraits de code montrant comment utiliser les principales fonctionnalités
4. Des conseils pour la résolution des problèmes courants
5. Des bonnes pratiques d'utilisation{elements_summary}

Voici le code à documenter :
```{self.file_info.language}
{self.file_info.content}
```"""
        }

        return prompts.get(doc_type, prompts['complete'])

    def save_documentation(self, content: str, output_file: str = None) -> str:
        """
        Sauvegarde la documentation générée dans un fichier.

        Args:
            content: Contenu de la documentation
            output_file: Chemin du fichier de sortie (optionnel)

        Returns:
            Chemin du fichier de sortie
        """
        if not output_file:
            # Générer un nom de fichier par défaut
            base_name = os.path.splitext(self.file_info.file_name)[0]
            output_file = f"{base_name}_documentation.md"

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)

            if self.console:
                self.console.print(f"[success]Documentation sauvegardée dans {output_file}[/success]")

            return output_file
        except Exception as e:
            if self.console:
                self.console.print(f"[error]Erreur lors de la sauvegarde de la documentation: {str(e)}[/error]")
            raise

    def process_documentation(self, response: str, doc_format: str = 'markdown') -> str:
        """
        Traite la réponse de Claude pour extraire et formater la documentation.

        Args:
            response: Réponse de Claude
            doc_format: Format de la documentation

        Returns:
            Documentation formatée
        """
        # Extraire le bloc de documentation de la réponse de Claude
        if doc_format == 'markdown':
            # Essayer d'extraire un bloc de code markdown
            md_pattern = r'```markdown\s*([\s\S]+?)\s*```'
            match = re.search(md_pattern, response)

            if match:
                return match.group(1)
            else:
                # Si pas de bloc markdown spécifique, essayer d'extraire tout le contenu utile
                # en supprimant les parties introductives ou explicatives
                lines = response.split('\n')
                # Ignorer les lignes de début qui sont des explications
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('#') or line.startswith('---'):
                        start_idx = i
                        break

                # Ignorer les lignes de fin qui sont des conclusions
                end_idx = len(lines)
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].lower().startswith(('voici', 'voilà', 'j\'espère', 'n\'hésitez')):
                        end_idx = i
                        break

                return '\n'.join(lines[start_idx:end_idx])

        # Pour les autres formats (HTML, RST, etc.)
        # On pourrait ajouter d'autres logiques d'extraction spécifiques

        # Par défaut, retourner la réponse complète
        return response


class ProjectAnalyzer:
    """Classe pour analyser un projet entier (plusieurs fichiers)"""

    DEFAULT_EXCLUDED_DIRS = ['.git', '.github', '.vscode', 'node_modules', 'venv', '__pycache__', 'dist', 'build', '.venv', 'vendor', 'var', 'logs']
    DEFAULT_EXCLUDED_FILES = ['.gitignore', '.DS_Store', 'package-lock.json', 'yarn.lock', 'symfony.lock', 'composer.lock']

    def __init__(self, project_dir: str, console=None, excluded_dirs=None, excluded_files=None):
        """
        Initialise l'analyseur de projet.

        Args :
            project_dir : Chemin vers le répertoire du projet
            console : Objet console pour l'affichage (optionnel)
        """
        self.project_dir = project_dir
        self.console = console
        self.code_analyzer = CodeAnalyzer(console)
        self.files = []
        self.excluded_dirs = excluded_dirs if excluded_dirs is not None else self.DEFAULT_EXCLUDED_DIRS.copy()
        self.excluded_files = excluded_files if excluded_files is not None else self.DEFAULT_EXCLUDED_FILES.copy()

    def scan_project(self, file_extensions: List[str] = None) -> List[Dict[str, Any]]:
        """
        Scanne le projet pour trouver tous les fichiers de code.

        Args :
            file_extensions : Liste d'extensions à inclure (ex: ['.py', '.js'])

        Returns :
            Liste des informations sur les fichiers trouvés
        """
        self.files = []

        if self.console:
            self.console.print(f"[info]Scan du projet: {self.project_dir}[/info]")

        for root, dirs, files in os.walk(self.project_dir):
            # Exclure les répertoires à ignorer
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]

            for filename in files:
                # Vérifier si le fichier doit être exclu
                if filename in self.excluded_files:
                    continue

                # Vérifier l'extension si spécifiée
                if file_extensions:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in file_extensions:
                        continue

                file_path = os.path.join(root, filename)
                try:
                    file_info = FileInfo(file_path)
                    # Ne pas charger le contenu tout de suite pour économiser la mémoire
                    self.files.append(file_info.get_summary())
                except Exception as e:
                    if self.console:
                        self.console.print(f"[warning]Erreur lors de l'analyse de {file_path}: {str(e)}[/warning]")

        if self.console:
            self.console.print(f"[info]Scan terminé: {len(self.files)} fichiers trouvés[/info]")

        return self.files

    def generate_project_summary_prompt(self) -> str:
        """
        Génère un prompt pour l'analyse du projet.

        Returns :
            Prompt formaté pour Claude
        """
        if not self.files:
            raise ValueError("Aucun fichier trouvé. Utilisez scan_project() d'abord.")

        # Créer un résumé du projet
        languages = {}
        total_lines = 0

        for file in self.files:
            lang = file.get('language', 'unknown')
            lines = file.get('line_count', 0)

            languages[lang] = languages.get(lang, 0) + 1
            total_lines += lines

        # Trier les langages par nombre de fichiers
        languages_summary = ", ".join([f"{count} fichiers {lang}" for lang, count in
                                       sorted(languages.items(), key=lambda x: x[1], reverse=True)])

        # Sélectionner quelques fichiers représentatifs pour analyse détaillée
        main_files = []
        for lang in languages.keys():
            # Trouver les fichiers les plus importants pour chaque langage
            lang_files = [f for f in self.files if f.get('language') == lang]
            if lang_files:
                # Trier par nombre de lignes (indicateur basique d'importance)
                lang_files.sort(key=lambda x: x.get('line_count', 0), reverse=True)
                main_files.extend(lang_files[:min(2, len(lang_files))])

        # Limiter à 5 fichiers maximum
        main_files = main_files[:5]

        # Charger le contenu des fichiers principaux
        files_content = ""
        for file_info in main_files:
            file_path = file_info['file_path']
            try:
                content = self.code_analyzer.load_file(file_path).content
                # Limiter la taille si nécessaire
                if len(content) > 5000:  # Environ 100 lignes
                    content = content[:5000] + "...\n[contenu tronqué pour raisons de taille]"

                files_content += f"\n\nFichier: {file_info['file_name']} ({file_info['language']}, {file_info['line_count']} lignes)\n"
                files_content += f"```{file_info['language']}\n{content}\n```"
            except Exception as e:
                files_content += f"\n\nFichier: {file_info['file_name']} - Erreur lors du chargement: {str(e)}"

        prompt = f"""Analyse ce projet de développement qui contient {len(self.files)} fichiers, totalisant environ {total_lines} lignes de code.
Les technologies principales sont: {languages_summary}.

Je te fournis quelques fichiers clés pour que tu puisses comprendre la structure et le but du projet.
{files_content}

Basé sur ces échantillons, fournis:
1. Une vue d'ensemble du projet - son but, son architecture et ses fonctionnalités principales
2. Une analyse technique des choix d'implémentation et des patterns utilisés
3. Des recommandations pour améliorer l'organisation, la maintenabilité ou les performances
4. Des suggestions pour la documentation, les tests ou des fonctionnalités manquantes
5. Une feuille de route proposée pour les prochaines étapes de développement
"""

        return prompt