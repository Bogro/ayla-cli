import os

from src.core.handler.base_handler import BaseHandler
from src.services.client import AnthropicClient


class AnalyzePatterns(BaseHandler):

    def __init__(self, config, client, ui, api_key, crew_manager, code_analysis_available, pattern_analyzer):
        super().__init__(config, client, ui, api_key)
        self.code_analysis_available = code_analysis_available
        self.pattern_analyzer = pattern_analyzer
        self.crew_manager = crew_manager

    async def process(self, args):
        """Analyse les design patterns dans un fichier de code"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        file_path = args.patterns_analyze
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(self.api_key)
            if not self.client:
                self.ui.print_error("Impossible d'initialiser le client Anthropic. Vérifiez votre clé API.")
                return

        try:
            # Charger le fichier
            file_info = self.pattern_analyzer.load_file(file_path)
            self.ui.print_info(
                f"Analyse des patterns dans: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Analyser les patterns
            patterns_results = self.pattern_analyzer.detect_patterns_in_file()

            # Afficher les résultats initiaux
            detected_patterns = patterns_results['detected_patterns']
            if detected_patterns:
                self.ui.print_success(f"Patterns détectés ({len(detected_patterns)}):")
                for pattern in detected_patterns:
                    self.ui.console.print(f"[bold green]• {pattern['name']}[/bold green]: {pattern['description']}")
            else:
                self.ui.print_warning("Aucun pattern clairement identifié dans ce fichier.")

            # Afficher les suggestions
            suggested_patterns = patterns_results['suggested_patterns']
            if suggested_patterns:
                self.ui.print_info(f"Suggestions de patterns ({len(suggested_patterns)}):")
                for pattern in suggested_patterns:
                    self.ui.console.print(f"[bold blue]• {pattern['name']}[/bold blue]: {pattern['description']}")

            # Générer le prompt pour une analyse plus approfondie
            prompt = self.pattern_analyzer.generate_pattern_analysis_prompt()

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task("Analyse des patterns", total=None)
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
                    f.write(f"# Analyse des patterns de conception dans {file_path}\n\n")

                    # Écrire les patterns détectés
                    f.write("## Patterns détectés\n\n")
                    if detected_patterns:
                        for pattern in detected_patterns:
                            f.write(f"- **{pattern['name']}**: {pattern['description']}\n")
                    else:
                        f.write("Aucun pattern clairement identifié.\n")

                    # Écrire les suggestions
                    f.write("\n## Suggestions de patterns\n\n")
                    if suggested_patterns:
                        for pattern in suggested_patterns:
                            f.write(f"- **{pattern['name']}**: {pattern['description']}\n")
                    else:
                        f.write("Aucune suggestion de pattern.\n")

                    # Écrire l'analyse détaillée
                    f.write("\n## Analyse détaillée\n\n")
                    f.write(response)

                self.ui.print_success(f"Analyse sauvegardée dans: {args.pattern_output}")

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse des patterns: {str(e)}")
            if hasattr(args, 'debug') and args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
