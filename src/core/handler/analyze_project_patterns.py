import os

from src.core.handler.base_handler import BaseHandler
from src.core.modules.code_analysis import ProjectAnalyzer
from src.services.client import AnthropicClient


class AnalyzeProjectPatterns(BaseHandler):

    def __init__(self, client, ui, crew_manager, api_key, code_analysis_available, pattern_analyzer):
        super().__init__(client, ui, crew_manager, api_key)
        self.code_analysis_available = code_analysis_available
        self.pattern_analyzer = pattern_analyzer

    async def process(self, args):
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
            self.client = AnthropicClient(self.api_key)
            if not self.client:
                self.ui.print_error("Impossible d'initialiser le client Anthropic. Vérifiez votre clé API.")
                return

        try:
            # Créer l'analyseur de projet
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
            self.ui.print_success(
                f"Analyse terminée: {files_analyzed} fichiers analysés, {files_with_patterns} avec des patterns")

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
