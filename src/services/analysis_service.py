import os
from src.core.modules.code_analysis import CodeAnalyzer, DocumentationGenerator, ProjectAnalyzer, PatternAnalyzer


class AnalysisService:
    """Service pour l'analyse de code et la génération de documentation."""

    def __init__(self, config, ui):
        """Initialise le service avec la configuration et l'UI."""
        self.config = config
        self.ui = ui
        self.code_analyzer = CodeAnalyzer()
        self.doc_generator = DocumentationGenerator()
        self.project_analyzer = ProjectAnalyzer()
        self.pattern_analyzer = PatternAnalyzer()

    def initialize(self):
        """Initialise les composants d'analyse"""
        try:
            os.makedirs(self.config.DEFAULT_ANALYSIS_DIR, exist_ok=True)
            self.code_analyzer = CodeAnalyzer(self.ui.console)
            self.doc_generator = DocumentationGenerator(self.ui.console)
            self.project_analyzer = ProjectAnalyzer(self.ui.console)
            self.pattern_analyzer = PatternAnalyzer(self.ui.console)
            return True
        except ImportError:
            return False

    async def analyze_code(self, file_path, analysis_type, api_client):
        """Analyse un fichier de code."""
        if not os.path.exists(file_path):
            self.ui.print_error(
                f"Le fichier {file_path} n'existe pas."
            )
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            return await self._perform_code_analysis(
                code_content, analysis_type, api_client
            )
        except Exception as e:
            self.ui.print_error(
                f"Erreur lors de l'analyse: {str(e)}"
            )
            return None

    async def generate_documentation(
        self, file_path, doc_format, doc_type, api_client
    ):
        """Génère la documentation pour un fichier."""
        if not os.path.exists(file_path):
            name = os.path.basename(file_path)
            msg = f"Fichier introuvable: {name}"
            self.ui.print_error(msg)
            return None

        try:
            file_info = self.doc_generator.load_file(file_path)
            name = os.path.basename(file_path)
            lang = file_info.language
            lines = file_info.line_count
            
            desc = f"({lang}, {lines} lignes)"
            msg = f"Documentation: {name}\n{desc}"
            self.ui.print_info(msg)
            
            prompt = self.doc_generator.generate_documentation_prompt(
                doc_format, doc_type
            )
            model = self.config.DEFAULT_MODEL
            max_tokens = self.config.DEFAULT_MAX_TOKENS
            temp = self.config.DEFAULT_TEMPERATURE
            msg = [{"role": "user", "content": prompt}]
            
            resp = await api_client.send_message(
                model, 
                msg, 
                max_tokens, 
                temp
            )
            
            return self.doc_generator.process_documentation(
                resp, 
                doc_format
            )
        except Exception as e:
            msg = f"Erreur: {str(e)}"
            self.ui.print_error(msg)
            return None

    async def analyze_project(self, project_dir, api_client):
        """Analyse un projet entier."""
        if not os.path.isdir(project_dir):
            name = os.path.basename(project_dir)
            msg = f"Répertoire invalide: {name}"
            self.ui.print_error(msg)
            return None

        try:
            info = {}
            info['structure'] = self._get_project_structure(
                project_dir
            )
            info['dependencies'] = self._get_project_dependencies(
                project_dir
            )
            info['tech_stack'] = self._get_tech_stack(
                project_dir
            )
            info['documentation'] = self._get_project_documentation(
                project_dir
            )
            
            return await self._perform_project_analysis(
                info, 
                api_client
            )
        except Exception as e:
            msg = f"Erreur: {str(e)}"
            self.ui.print_error(msg)
            return None

    def _get_project_structure(self, project_dir):
        """Obtient la structure du projet"""
        structure = []
        for root, dirs, files in os.walk(project_dir):
            level = root.replace(project_dir, '').count(os.sep)
            indent = '  ' * level
            structure.append(f"{indent}{os.path.basename(root)}/")
            for file in files:
                structure.append(f"{indent}  {file}")
        return '\n'.join(structure)

    def _get_project_dependencies(self, project_dir):
        """Obtient les dépendances du projet"""
        dependencies = []
        
        # Vérifier requirements.txt
        req_file = os.path.join(project_dir, 'requirements.txt')
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                dependencies.append("Python dependencies (requirements.txt):")
                dependencies.extend(f.readlines())

        # Vérifier package.json
        pkg_file = os.path.join(project_dir, 'package.json')
        if os.path.exists(pkg_file):
            import json
            with open(pkg_file, 'r') as f:
                pkg_data = json.load(f)
                if 'dependencies' in pkg_data:
                    dependencies.append("\nNode.js dependencies:")
                    for dep, version in pkg_data['dependencies'].items():
                        dependencies.append(f"{dep}: {version}")

        return '\n'.join(dependencies) if dependencies else "No dependencies found"

    def _get_tech_stack(self, project_dir):
        """Identifie la stack technologique"""
        tech_stack = []
        extensions = {}
        
        for root, _, files in os.walk(project_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1

        tech_mapping = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React',
            '.tsx': 'React with TypeScript',
            '.vue': 'Vue.js',
            '.go': 'Go',
            '.rs': 'Rust',
            '.java': 'Java',
            '.kt': 'Kotlin',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.cs': 'C#',
            '.cpp': 'C++',
            '.c': 'C',
        }

        for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
            if ext in tech_mapping:
                tech_stack.append(f"{tech_mapping[ext]} ({count} files)")

        return '\n'.join(tech_stack) if tech_stack else "No tech stack identified"

    def _get_project_documentation(self, project_dir):
        """Collecte la documentation du projet"""
        docs = []
        doc_files = ['README.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'API.md', 'docs/']
        
        for doc in doc_files:
            path = os.path.join(project_dir, doc)
            if os.path.exists(path):
                if os.path.isfile(path):
                    with open(path, 'r') as f:
                        docs.append(f"\n=== {doc} ===\n")
                        docs.append(f.read())
                elif os.path.isdir(path):
                    docs.append(f"\n=== Documentation in {doc} ===\n")
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.endswith(('.md', '.rst', '.txt')):
                                file_path = os.path.join(root, file)
                                with open(file_path, 'r') as f:
                                    docs.append(f"\n--- {file} ---\n")
                                    docs.append(f.read())

        return '\n'.join(docs) if docs else "No documentation found"

    async def _perform_code_analysis(self, code_content, analysis_type, api_client):
        """Effectue l'analyse du code"""
        # Cette méthode serait implémentée avec la logique d'analyse spécifique
        pass

    async def _perform_project_analysis(self, project_info, api_client):
        """Effectue l'analyse du projet"""
        # Cette méthode serait implémentée avec la logique d'analyse spécifique
        pass 