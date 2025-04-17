import os

from src.core.handler.base_handler import BaseHandler
from src.services.client import AnthropicClient


class CodeAnalyzerHandler(BaseHandler):

    def __init__(self, config, client, ui, api_key, crew_manager):
        super().__init__(config, client, ui, api_key)
        self.crew_manager = crew_manager

    async def process(self, args):
        """Analyse un fichier de code avec Ayla"""
        # Vérifier si le module d'analyse de code est disponible
        # if not self.code_analysis_available:
        #     self.ui.print_error(
        #         "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
        #     return

        file_path = args.analyze
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            self.client = AnthropicClient(self.api_key)

        # Créer l'analyseur de code
        from src.core.modules.code_analysis import CodeAnalyzer
        analyzer = CodeAnalyzer(self.ui.console)

        try:
            # Charger le fichier
            file_info = analyzer.load_file(file_path)
            self.ui.print_info(f"Analyse du fichier: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Générer le prompt d'analyse
            analysis_type = args.analysis_type
            analysis_crew = args.analysis_crew

            prompt = analyzer.generate_analysis_prompt(analysis_type)

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task(f"Analyse {analysis_type}", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Afficher la réponse
            self.ui.print_assistant_response(response, args.raw)

            # Déterminer le dossier de sortie
            output_dir = None
            if hasattr(args, 'output_dir') and args.output_dir:
                output_dir = args.output_dir
            elif hasattr(self.config, 'ANALYSIS_DIR'):
                output_dir = self.config.ANALYSIS_DIR

            # Créer le dossier de sortie s'il existe et n'existe pas déjà
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Sauvegarder la réponse
            if hasattr(args, 'output') and args.output:
                # Si output_dir est spécifié et args.output n'est pas un chemin absolu, combiner les deux
                if output_dir and not os.path.isabs(args.output):
                    output_file = os.path.join(output_dir, args.output)
                else:
                    output_file = args.output

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")
            elif hasattr(args, 'auto_save') and args.auto_save:
                base_name = os.path.splitext(os.path.basename(file_path))[0]

                # Si output_dir est spécifié, l'utiliser; sinon, utiliser le répertoire courant
                if output_dir:
                    output_file = os.path.join(output_dir, f"{base_name}_analysis_{analysis_type}.md")
                else:
                    output_file = f"{base_name}_analysis_{analysis_type}.md"

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(response)
                self.ui.print_success(f"Analyse sauvegardée dans le fichier: {output_file}")

            return response

        except Exception as e:
            self.ui.print_error(f"Erreur lors de l'analyse du code: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
            return None

    async def _crew_analyze_code(self, args):
        """Analyse un fichier de code"""
        if not args.analyze:
            return

        file_path = args.analyze
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        try:
            # Lire le contenu du fichier
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()

            self.crew_manager.init_llm(self.api_key)

            # Créer une équipe d'analyse avec CrewAI
            crew = self.crew_manager.create_code_analysis_crew(
                code=code_content,
                analysis_type=args.analysis_type
            )

            # Lancer l'analyse
            with self.ui.create_progress() as progress:
                task = progress.add_task(f"Analyse {args.analysis_type}", total=None)

            result = crew.kickoff()

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
