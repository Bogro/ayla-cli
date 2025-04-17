import os
import re
from typing import List, Dict, Any

from src.utils.file_info import FileInfo


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
                f"[info]Fichier chargé: {file_path} "
                f"({self.file_info.language}, {self.file_info.line_count} lignes)[/info]"
            )

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
                    elements_summary += (
                        f" et les fonctions suivantes : {functions_str}"
                    )
                else:
                    elements_summary += (
                        f"les fonctions suivantes : {functions_str}"
                    )
            elements_summary += (
                ". Assure-toi de documenter ces éléments en détail."
            )

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

    def add_exclude_dirs(self, exclude_dirs):
        pass

    def add_exclude_files(self, exclude_files):
        pass

    def set_extensions(self, extensions):
        pass

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


class PatternAnalyzer:
    """Classe pour analyser et suggérer des design patterns dans le code"""

    # Définition des patterns communs et leurs signatures
    COMMON_PATTERNS = {
        'singleton': {
            'description': (
                "Un pattern qui garantit qu'une classe n'a qu'une seule "
                "instance et fournit un point d'accès global"
            ),
            'languages': {
                'python': [
                    r'_instance\s*=\s*None',
                    r'if\s+cls\._instance\s+is\s+None',
                    r'@classmethod\s+def\s+get_instance\s*\(',
                    r'return\s+cls\._instance',
                ],
                'javascript': [
                    r'static\s+instance\s*=\s*null',
                    r'if\s*\(\s*!this\.instance\s*\)',
                    r'return\s+this\.instance',
                    r'getInstance\s*\(\s*\)'
                ],
                'java': [
                    r'private\s+static\s+\w+\s+instance',
                    r'return\s+instance',
                    r'getInstance\(\)'
                ]
            }
        },
        'factory': {
            'description': (
                "Un pattern qui définit une interface pour créer un objet, "
                "mais laisse les sous-classes décider quelles classes "
                "instancier"
            ),
            'languages': {
                'python': [
                    r'def\s+create',
                    r'@abstractmethod',
                    r'return\s+\w+\(\)',
                    r'class\s+\w+Factory'
                ],
                'javascript': [
                    r'class\s+\w+Factory',
                    r'create\w+\s*\(',
                    r'return\s+new\s+\w+\(',
                ],
                'java': [
                    r'interface\s+\w+Factory',
                    r'abstract\s+\w+\s+create\w+\(',
                    r'new\s+\w+\('
                ]
            }
        },
        'observer': {
            'description': (
                "Un pattern qui définit une dépendance un-à-plusieurs entre "
                "objets, de sorte que lorsqu'un objet change d'état, tous "
                "ses dépendants sont notifiés"
            ),
            'languages': {
                'python': [
                    r'def\s+add_observer',
                    r'def\s+remove_observer',
                    r'def\s+notify',
                    r'observers\s*=\s*\[\]',
                    r'for\s+observer\s+in\s+'
                ],
                'javascript': [
                    r'addObserver|addEventListener|on\(',
                    r'removeObserver|removeEventListener|off\(',
                    r'notify|emit|trigger\(',
                    r'this\.observers\s*=',
                    r'subscribe|unsubscribe'
                ],
                'java': [
                    r'addObserver|addEventListener',
                    r'removeObserver|removeEventListener',
                    r'notify|update',
                    r'List<\w+>\s+observers'
                ]
            }
        },
        'strategy': {
            'description': (
                "Un pattern qui définit une famille d'algorithmes, encapsule "
                "chacun d'eux et les rend interchangeables"
            ),
            'languages': {
                'python': [
                    r'class\s+\w+Strategy',
                    r'def\s+execute\(',
                    r'self\.strategy\s*=',
                    r'self\.strategy\.execute\('
                ],
                'javascript': [
                    r'class\s+\w+Strategy',
                    r'execute\(',
                    r'this\.strategy\s*=',
                    r'this\.strategy\.execute\('
                ],
                'java': [
                    r'interface\s+\w+Strategy',
                    r'implements\s+\w+Strategy',
                    r'this\.strategy\s*=',
                    r'strategy\.execute\('
                ]
            }
        },
        'decorator': {
            'description': (
                "Un pattern qui permet d'ajouter dynamiquement des "
                "responsabilités à un objet sans modifier son interface"
            ),
            'languages': {
                'python': [
                    r'@\w+',
                    r'def\s+wrapper\(',
                    r'class\s+\w+Decorator',
                    r'super\(\)\.\w+\('
                ],
                'javascript': [
                    r'@\w+',
                    r'class\s+\w+Decorator',
                    r'this\.wrapped\s*=',
                    r'function\s+decorate\(',
                    r'Object\.assign\('
                ],
                'java': [
                    r'extends\s+\w+Decorator',
                    r'this\.wrapped\s*=',
                    r'super\.\w+\('
                ]
            }
        },
        'adapter': {
            'description': (
                "Un pattern qui convertit l'interface d'une classe en une autre "
                "interface attendue par les clients"
            ),
            'languages': {
                'python': [
                    r'class\s+\w+Adapter',
                    r'def\s+__init__\s*\(\s*self\s*,\s*\w+\s*\)',
                    r'self\.\w+\.\w+\('
                ],
                'javascript': [
                    r'class\s+\w+Adapter',
                    r'constructor\s*\(\s*\w+\s*\)',
                    r'this\.\w+\.\w+\('
                ],
                'java': [
                    r'class\s+\w+Adapter',
                    r'implements\s+\w+',
                    r'private\s+\w+\s+\w+;'
                ]
            }
        }
    }

    def __init__(self, console=None):
        """
        Initialise l'analyseur de patterns.

        Args:
            console: Objet console pour l'affichage (optionnel)
        """
        self.console = console
        self.code_analyzer = CodeAnalyzer(console)
        self.file_info = None
        self.project_analyzer = None

    def load_file(self, file_path: str) -> FileInfo:
        """
        Charge un fichier pour analyse.

        Args:
            file_path: Chemin vers le fichier à analyser

        Returns:
            Objet FileInfo contenant les informations du fichier
        """
        self.file_info = self.code_analyzer.load_file(file_path)
        return self.file_info

    def set_project_analyzer(self, project_analyzer):
        """
        Définit l'analyseur de projet pour analyser plusieurs fichiers.

        Args:
            project_analyzer: Analyseur de projet à utiliser
        """
        self.project_analyzer = project_analyzer

    def detect_patterns_in_file(self) -> Dict[str, Any]:
        """
        Détecte les patterns de conception potentiels dans un fichier.

        Returns:
            Résultats de l'analyse avec patterns détectés et suggestions
        """
        if not self.file_info or not self.file_info.content:
            raise ValueError("Aucun fichier chargé. Utilisez load_file() d'abord.")

        content = self.file_info.content
        language = self.file_info.language
        
        results = {
            'file_path': self.file_info.file_path,
            'language': language,
            'detected_patterns': [],
            'suggested_patterns': [],
            'architectural_hints': []
        }
        
        # Analyser chaque pattern connu
        for pattern_name, pattern_info in self.COMMON_PATTERNS.items():
            if language in pattern_info['languages']:
                # Vérifier les signatures pour ce langage
                signatures = pattern_info['languages'][language]
                matches = 0
                for signature in signatures:
                    if re.search(signature, content, re.MULTILINE):
                        matches += 1
                
                # Si plus de la moitié des signatures sont trouvées, considérer comme un match
                confidence_threshold = len(signatures) / 2
                if matches > confidence_threshold:
                    results['detected_patterns'].append({
                        'name': pattern_name,
                        'description': pattern_info['description'],
                        'confidence': matches / len(signatures)
                    })
                # Sinon, suggérer comme possibilité si au moins une signature est trouvée
                elif matches > 0:
                    results['suggested_patterns'].append({
                        'name': pattern_name,
                        'description': pattern_info['description'],
                        'confidence': matches / len(signatures)
                    })
                    
        # Analyser les opportunités d'amélioration
        self._analyze_opportunities(results)
                    
        return results
    
    def _analyze_opportunities(self, results: Dict[str, Any]):
        """
        Analyse les opportunités d'amélioration architecturale.
        
        Args:
            results: Résultats de l'analyse des patterns
        """
        if not self.file_info or not self.file_info.content:
            return
            
        content = self.file_info.content
        language = self.file_info.language
        
        # Détection de code qui pourrait bénéficier du pattern Singleton
        detected_patterns = [p['name'] for p in results['detected_patterns']]
        if 'singleton' not in detected_patterns:
            # Recherche de variables globales ou classes avec des méthodes statiques
            if language == 'python':
                has_global_vars = re.search(r'^\w+\s*=', content, re.MULTILINE)
                has_functions = re.search(r'def\s+\w+\(', content, re.MULTILINE)
                if has_global_vars and has_functions:
                    hint = (
                        "Des variables globales sont utilisées. Un Singleton "
                        "pourrait encapsuler cet état global."
                    )
                    results['architectural_hints'].append({
                        'pattern': 'singleton',
                        'hint': hint
                    })
            elif language in ['javascript', 'typescript']:
                has_const = re.search(r'const\s+\w+\s*=', content, re.MULTILINE)
                has_export = re.search(r'export\s+default', content, re.MULTILINE)
                if has_const and has_export:
                    hint = (
                        "Un module exporté par défaut avec des constantes "
                        "pourrait être transformé en Singleton."
                    )
                    results['architectural_hints'].append({
                        'pattern': 'singleton',
                        'hint': hint
                    })
                    
        # Détection de code qui pourrait bénéficier du pattern Factory
        if 'factory' not in detected_patterns:
            # Recherche de multiples instanciations du même type
            if language == 'python':
                classes = re.findall(r'class\s+(\w+)', content)
                for cls in classes:
                    if re.findall(rf'{cls}\s*\(', content, re.MULTILINE):
                        hint = (
                            f"Plusieurs instanciations de '{cls}' détectées. "
                            f"Un Factory Method pourrait simplifier la "
                            f"création d'objets."
                        )
                        results['architectural_hints'].append({
                            'pattern': 'factory',
                            'hint': hint
                        })
                        break
            elif language in ['javascript', 'typescript']:
                classes = re.findall(r'class\s+(\w+)', content)
                for cls in classes:
                    pattern = rf'new\s+{cls}\s*\('
                    if re.findall(pattern, content, re.MULTILINE):
                        hint = (
                            f"Plusieurs instanciations de '{cls}' détectées. "
                            f"Un Factory Method pourrait simplifier la "
                            f"création d'objets."
                        )
                        results['architectural_hints'].append({
                            'pattern': 'factory',
                            'hint': hint
                        })
                        break
                        
        # Détection de code qui pourrait bénéficier du pattern Strategy
        if 'strategy' not in detected_patterns:
            # Recherche de structures conditionnelles complexes
            if re.findall(r'if.*?else if.*?else if', content, re.DOTALL):
                hint = (
                    "Structures conditionnelles complexes détectées. Le pattern "
                    "Strategy pourrait rendre le code plus maintenable."
                )
                results['architectural_hints'].append({
                    'pattern': 'strategy',
                    'hint': hint
                })
                
        # Détection de code qui pourrait bénéficier du pattern Observer
        if 'observer' not in detected_patterns:
            # Recherche de code qui pourrait bénéficier d'événements
            if language == 'python':
                has_update = re.search(r'def\s+update\(.*\):', content, re.MULTILINE)
                has_notify = re.search(r'def\s+notify\(.*\):', content, re.MULTILINE)
                if has_update or has_notify:
                    hint = (
                        "Le code contient des mécanismes de mise à jour/"
                        "notification. Le pattern Observer pourrait améliorer "
                        "la séparation des préoccupations."
                    )
                    results['architectural_hints'].append({
                        'pattern': 'observer',
                        'hint': hint
                    })
            elif language in ['javascript', 'typescript']:
                has_update = re.search(
                    r'function\s+update\(.*\)', 
                    content, 
                    re.MULTILINE
                )
                has_onChange = re.search(r'onChange\s*\(', content, re.MULTILINE)
                if has_update or has_onChange:
                    hint = (
                        "Le code contient des mécanismes de mise à jour/"
                        "notification. Le pattern Observer pourrait améliorer "
                        "la séparation des préoccupations."
                    )
                    results['architectural_hints'].append({
                        'pattern': 'observer',
                        'hint': hint
                    })

    def analyze_project_patterns(self) -> Dict[str, Any]:
        """
        Analyse les patterns dans tout le projet.

        Returns:
            Résumé des patterns détectés au niveau du projet
        """
        if not self.project_analyzer:
            msg = "Aucun analyseur de projet défini. Utilisez set_project_analyzer() d'abord."
            raise ValueError(msg)
            
        # Récupérer tous les fichiers du projet
        all_files = self.project_analyzer.files
        if not all_files:
            all_files = self.project_analyzer.scan_project()
            
        # Initialiser les résultats
        project_results = {
            'project_dir': self.project_analyzer.project_dir,
            'files_analyzed': 0,
            'detected_patterns': {},
            'suggested_improvements': [],
            'architectural_overview': [],
            'files_with_patterns': []
        }
        
        # Analyser chaque fichier
        for file_info in all_files:
            try:
                file_path = file_info['file_path']
                self.load_file(file_path)
                
                # Analyser les patterns dans ce fichier
                file_results = self.detect_patterns_in_file()
                project_results['files_analyzed'] += 1
                
                # Si des patterns ont été détectés, ajouter aux résultats du projet
                has_patterns = (
                    file_results['detected_patterns'] or 
                    file_results['suggested_patterns']
                )
                if has_patterns:
                    project_results['files_with_patterns'].append({
                        'file_path': file_path,
                        'patterns': file_results['detected_patterns'],
                        'suggestions': file_results['suggested_patterns']
                    })
                    
                    # Mettre à jour le compteur de patterns
                    for pattern in file_results['detected_patterns']:
                        name = pattern['name']
                        if name in project_results['detected_patterns']:
                            project_results['detected_patterns'][name]['count'] += 1
                            files = project_results['detected_patterns'][name]['files']
                            files.append(file_path)
                        else:
                            project_results['detected_patterns'][name] = {
                                'count': 1,
                                'description': pattern['description'],
                                'files': [file_path]
                            }
                            
                # Collecter les suggestions d'amélioration
                for hint in file_results['architectural_hints']:
                    project_results['suggested_improvements'].append({
                        'file_path': file_path,
                        'pattern': hint['pattern'],
                        'hint': hint['hint']
                    })
                    
            except Exception as e:
                if self.console:
                    err_msg = (
                        f"[warning]Erreur lors de l'analyse des patterns dans "
                        f"{file_path}: {str(e)}[/warning]"
                    )
                    self.console.print(err_msg)
        
        # Générer un aperçu architectural
        self._generate_architectural_overview(project_results)
        
        return project_results
        
    def _generate_architectural_overview(self, results: Dict[str, Any]):
        """
        Génère un aperçu architectural basé sur les patterns détectés.

        Args:
            results: Résultats de l'analyse du projet
        """
        # Définir des recommandations architecturales en fonction des patterns détectés
        if not results['detected_patterns']:
            msg = (
                "Aucun pattern de conception clairement identifié. L'architecture "
                "pourrait bénéficier de l'introduction de patterns."
            )
            results['architectural_overview'].append(msg)
        else:
            # Analyser les patterns les plus courants
            common_patterns = sorted(
                results['detected_patterns'].items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            # Générer des suggestions spécifiques
            if len(common_patterns) >= 3:
                patterns_names = [p[0] for p in common_patterns[:3]]
                patterns_str = ', '.join(patterns_names)
                msg1 = f"Le projet utilise principalement les patterns: "
                msg2 = f"{patterns_str}. "
                msg3 = (
                    "Cela suggère une architecture bien structurée avec une "
                    "séparation des préoccupations."
                )
                results['architectural_overview'].append(msg1 + msg2 + msg3)
            
            # Détection des anti-patterns architecturaux
            detected_pattern_names = set(results['detected_patterns'].keys())
            
            # Utilisation de Singleton sans Factory
            singleton_without_factory = (
                'singleton' in detected_pattern_names and 
                'factory' not in detected_pattern_names
            )
            if singleton_without_factory:
                msg1 = "Le pattern Singleton est utilisé sans Factory Method. "
                msg2 = "Cela pourrait indiquer un couplage fort. "
                msg3 = (
                    "Considérez l'introduction du pattern Factory pour améliorer "
                    "la flexibilité."
                )
                results['architectural_overview'].append(msg1 + msg2 + msg3)
                
            # Manque de patterns d'extension
            ext_patterns = {'decorator', 'strategy', 'observer'} & detected_pattern_names
            if not ext_patterns:
                msg1 = (
                    "Aucun pattern d'extension (Decorator, Strategy, Observer) "
                    "n'a été détecté. "
                )
                msg2 = (
                    "Ces patterns pourraient améliorer l'extensibilité et "
                    "la maintenabilité du code."
                )
                results['architectural_overview'].append(msg1 + msg2)
                
        # Ajouter des recommandations générales basées sur la taille du projet
        files_count = results['files_analyzed']
        if files_count > 50:
            msg1 = f"Projet de taille importante ({files_count} fichiers). "
            msg2 = "Considérez l'adoption d'une architecture modulaire "
            msg3 = "avec des frontières claires entre les composants."
            results['architectural_overview'].append(msg1 + msg2 + msg3)
        elif files_count > 10:
            msg1 = f"Projet de taille moyenne ({files_count} fichiers). "
            msg2 = "Une architecture orientée composants avec des patterns "
            msg3 = "comme Factory et Observer pourrait être bénéfique."
            results['architectural_overview'].append(msg1 + msg2 + msg3)
            
        # Recommandations basées sur les améliorations suggérées
        if results['suggested_improvements']:
            patterns = set(
                item['pattern'] 
                for item in results['suggested_improvements']
            )
            if patterns:
                patterns_text = ", ".join(patterns)
                msg1 = (
                    "Basé sur le code existant, l'introduction des patterns "
                    f"suivants pourrait être bénéfique: {patterns_text}."
                )
                results['architectural_overview'].append(msg1)

    def generate_pattern_analysis_prompt(self, file_path: str = None) -> str:
        """
        Génère un prompt pour une analyse de patterns plus approfondie par Claude.

        Args:
            file_path: Chemin du fichier à analyser (optionnel, utilise le fichier 
                     courant si non spécifié)

        Returns:
            Prompt formaté pour Claude
        """
        if file_path:
            self.load_file(file_path)
            
        if not self.file_info or not self.file_info.content:
            msg = "Aucun fichier chargé. Utilisez load_file() d'abord."
            raise ValueError(msg)
            
        # Résultats de l'analyse préliminaire
        analysis = self.detect_patterns_in_file()
        
        # Construire le prompt
        detected = [p['name'] for p in analysis['detected_patterns']]
        detected_patterns = ", ".join(detected)
        
        suggested = [p['name'] for p in analysis['suggested_patterns']]
        suggested_patterns = ", ".join(suggested)
        
        prompt = f"""Analyse ce code {self.file_info.language} du point de vue des design patterns.

Mon analyse préliminaire a détecté les patterns suivants: {detected_patterns or "aucun"}.
Elle suggère également l'utilisation potentielle de: {suggested_patterns or "aucun"}.

Dans ton analyse, je voudrais que tu:
1. Identifies tous les design patterns utilisés dans ce code
2. Expliques comment ils sont implémentés et s'ils sont bien appliqués
3. Suggères des améliorations ou des patterns alternatifs qui pourraient être plus appropriés
4. Proposes une structure améliorée du code avec des exemples concrets

Voici le code:
```{self.file_info.language}
{self.file_info.content}
```

Format ta réponse avec des sections claires pour chaque pattern identifié et les suggestions d'amélioration.
"""
        return prompt

    def generate_project_patterns_prompt(self) -> str:
        """
        Génère un prompt pour l'analyse des patterns au niveau projet.

        Returns:
            Prompt formaté pour Claude
        """
        if not self.project_analyzer:
            msg = (
                "Aucun analyseur de projet défini. "
                "Utilisez set_project_analyzer() d'abord."
            )
            raise ValueError(msg)
            
        # Analyser le projet
        project_analysis = self.analyze_project_patterns()
        
        # Construire la liste des fichiers avec leurs patterns détectés
        files_info = []
        # Limiter à 10 fichiers pour le prompt
        for file_data in project_analysis['files_with_patterns'][:10]:
            patterns = ", ".join([p['name'] for p in file_data['patterns']])
            files_info.append(f"- {file_data['file_path']}: {patterns}")
            
        files_text = "\n".join(files_info)
        files_count = len(project_analysis['files_with_patterns'])
        if files_count > 10:
            files_text += f"\n- ...et {files_count - 10} autres fichiers"
            
        # Construire le prompt
        detected = project_analysis['detected_patterns'].keys()
        detected_patterns = (
            ', '.join(detected) if detected 
            else "Aucun pattern clairement identifié"
        )
        
        prompt = f"""Analyse l'architecture et les design patterns de ce projet.

Le projet contient {project_analysis['files_analyzed']} fichiers, et j'ai détecté des patterns dans {len(project_analysis['files_with_patterns'])} d'entre eux.

Patterns principaux détectés:
{detected_patterns}

Fichiers avec patterns identifiés:
{files_text}

Dans ton analyse, je voudrais que tu:
1. Évalues la qualité architecturale globale du projet basée sur ces informations
2. Identifies les forces et faiblesses de l'architecture actuelle
3. Suggères des améliorations architecturales spécifiques
4. Proposes une structure améliorée avec les patterns appropriés
5. Fournis des exemples de refactoring pour les parties clés du projet

Aperçu architectural préliminaire:
{chr(10).join(project_analysis['architectural_overview'])}

Format ta réponse avec des sections claires pour l'évaluation globale, les suggestions d'amélioration, et des exemples concrets de refactoring.
"""
        return prompt