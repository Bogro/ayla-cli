import os

from src.core.handler.base_handler import BaseHandler
from src.core.modules.code_analysis import DocumentationGenerator
from src.services.client import AnthropicClient


class DocumentationGeneratorHandler(BaseHandler):

    def __init__(self, client, ui, crew_manager, api_key, code_analysis_available, config):
        super().__init__(client, ui, crew_manager, api_key)
        self.client = client
        self.ui = ui
        self.api_key = api_key
        self.config = config
        self.code_analysis_available = code_analysis_available

    async def process(self, args):
        """Génère de la documentation pour un fichier de code avec Ayla"""
        # Vérifier si le module d'analyse de code est disponible
        if not self.code_analysis_available:
            self.ui.print_error(
                "Module d'analyse de code non trouvé. Assurez-vous que code_analysis.py est dans le même répertoire.")
            return

        file_path = args.document
        if not os.path.exists(file_path):
            self.ui.print_error(f"Le fichier {file_path} n'existe pas.")
            return

        # Initialiser le client si ce n'est pas déjà fait
        if not self.client:
            client = AnthropicClient(self.api_key)

        # Créer le générateur de documentation
        doc_gen = DocumentationGenerator(self.ui.console)

        try:
            # Charger le fichier
            file_info = doc_gen.load_file(file_path)
            self.ui.print_info(
                f"Génération de documentation pour: {file_path} ({file_info.language}, {file_info.line_count} lignes)")

            # Générer le prompt de documentation
            doc_format = args.doc_format
            doc_type = args.doc_type
            prompt = doc_gen.generate_documentation_prompt(doc_format, doc_type)

            # Envoyer la requête
            with self.ui.create_progress() as progress:
                task = progress.add_task(f"Génération de documentation ({doc_type})", total=None)
                response = await self.client.send_message(
                    args.model,
                    [{"role": "user", "content": prompt}],
                    args.max_tokens,
                    args.temperature
                )

            # Traiter la réponse pour extraire la documentation
            doc_content = doc_gen.process_documentation(response, doc_format)

            # Afficher la réponse
            self.ui.print_assistant_response(doc_content, args.raw)

            # Déterminer le dossier de sortie
            output_dir = None
            if hasattr(args, 'output_dir') and args.output_dir:
                output_dir = args.output_dir
            elif hasattr(self.config, 'ANALYSIS_DIR'):
                output_dir = self.config.ANALYSIS_DIR

            # Créer le dossier de sortie s'il existe et n'existe pas déjà
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Sauvegarder la documentation
            if hasattr(args, 'output') and args.output:
                # Si output_dir est spécifié et args.output n'est pas un chemin absolu, combiner les deux
                if output_dir and not os.path.isabs(args.output):
                    output_file = os.path.join(output_dir, args.output)
                else:
                    output_file = args.output
            else:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                doc_extension = ".txt" if doc_format == 'rst' else f".{doc_format}"

                # Si output_dir est spécifié, l'utiliser; sinon, utiliser le répertoire courant
                if output_dir:
                    output_file = os.path.join(output_dir, f"{base_name}_documentation{doc_extension}")
                else:
                    output_file = f"{base_name}_documentation{doc_extension}"

            # Sauvegarder avec le générateur de documentation
            doc_gen.save_documentation(doc_content, output_file)
            self.ui.print_success(f"Documentation sauvegardée dans le fichier: {output_file}")

            return doc_content

        except Exception as e:
            self.ui.print_error(f"Erreur lors de la génération de documentation: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
            return None


