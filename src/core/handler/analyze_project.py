import os

from src.core.handler.base_handler import BaseHandler


class AnalyzeProjectHandler(BaseHandler):

    async def process(self, args):
        """Analyse un projet entier"""
        if not args.project:
            return

        project_dir = args.project
        if not os.path.isdir(project_dir):
            self.ui.print_error(f"Le répertoire {project_dir} n'existe pas.")
            return

        try:
            # Collecter les informations du projet
            project_info = {
                'structure': self._get_project_structure(project_dir),
                'dependencies': self._get_project_dependencies(project_dir),
                'tech_stack': self._get_tech_stack(project_dir),
                'documentation': self._get_project_documentation(project_dir)
            }

            # Créer une équipe d'analyse avec CrewAI
            crew = self.crew_manager.create_project_analysis_crew(project_info)

            # Lancer l'analyse
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse du projet", total=None)
                result = await crew.run()

            # Afficher et sauvegarder les résultats
            self.ui.print_assistant_response(result)

            if hasattr(args, 'output') and args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.ui.print_success(f"Analyse sauvegardée dans: {args.output}")

            return result

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())

    def _get_project_structure(self, project_dir: str) -> str:
        """Obtient la structure du projet."""
        structure = []
        for root, dirs, files in os.walk(project_dir):
            level = root.replace(project_dir, '').count(os.sep)
            indent = '  ' * level
            structure.append(f"{indent}{os.path.basename(root)}/")
            for file in files:
                structure.append(f"{indent}  {file}")
        return '\n'.join(structure)

    def _get_project_dependencies(self, project_dir: str) -> str:
        """Obtient les dépendances du projet."""
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

    def _get_tech_stack(self, project_dir: str) -> str:
        """Identifie la stack technologique du projet."""
        tech_stack = []

        # Détecter le langage principal
        extensions = {}
        for root, _, files in os.walk(project_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1

        # Mapper les extensions aux technologies
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

        return '\n'.join(tech_stack) if tech_stack else "Technology stack could not be determined"

    def _get_project_documentation(self, project_dir: str) -> str:
        """Collecte la documentation du projet."""
        docs = []

        # Chercher les fichiers de documentation courants
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

