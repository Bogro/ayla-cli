import sys

from anthropic import RateLimitError, APIStatusError, APIConnectionError, APIError

from src.core.modules.file_manager import FileManager
from src.core.modules.interactive import InteractiveMode
from src.services.client import AnthropicClient


class ProcessRequest:
    def __init__(self, client, ui, file_manager, conv_manager, streamer):
        self.client = client
        self.ui = ui
        self.file_manager = file_manager
        self.conv_manager = conv_manager
        self.streamer = streamer


    async def process_request(self, args, api_key):
        """Traite une requête à Ayla"""
        if not self.client:
            self.client = AnthropicClient(api_key)

        # Initialiser les classes dépendantes
        interactive_mode = InteractiveMode(self.ui, self.conv_manager, self.client, self.streamer)

        # Construire le message utilisateur
        prompt_text = " ".join(args.prompt)

        # Lire depuis l'entrée standard si nécessaire
        if not prompt_text and not sys.stdin.isatty():
            prompt_text = sys.stdin.read().strip()

        # Ajouter le contenu des fichiers si spécifiés
        if args.file:
            file_contents = []
            for file_path in args.file:
                content = self.file_manager.read_file_content(file_path)
                if content:
                    file_contents.append(f"Contenu du fichier {file_path}:\n\n{content}")

            if file_contents:
                if prompt_text:
                    prompt_text += "\n\n" + "\n\n".join(file_contents)
                else:
                    prompt_text = "\n\n".join(file_contents)

        # Vérifier si nous avons un message à envoyer
        if not prompt_text and not args.interactive and not args.continue_conversation:
            if args.conversation_id:
                # Si un ID de conversation est spécifié mais pas de prompt, afficher l'historique
                history = self.conv_manager.load_conversation_history(args.conversation_id)
                self.ui.display_conversation_history(history)
                return
            else:
                # Sinon, entrer en mode interactif
                args.interactive = True

        # Charger l'historique de conversation si nécessaire
        history = []
        if args.conversation_id:
            history = self.conv_manager.load_conversation_history(args.conversation_id)

        # Si on continue une conversation mais sans prompt, utiliser le mode interactif
        if args.continue_conversation and not prompt_text:
            args.interactive = True

        # Mode interactif
        if args.interactive:
            await interactive_mode.start(args, history, args.conversation_id)
            return

        # Ajouter le nouveau message à l'historique
        if prompt_text:
            history.append({"role": "user", "content": prompt_text})

        # Afficher le message utilisateur
        if not args.raw:
            self.ui.print_user(prompt_text)

        # Envoyer la requête et obtenir la réponse
        try:
            if args.stream:
                # Mode de débogage si demandé
                if args.debug:
                    response_text = await self.streamer.stream_assistant_response_debug(
                        self.client.get_client(), args.model, history, args.max_tokens, args.temperature, args.raw
                    )
                else:
                    response_text = await self.streamer.stream_assistant_response(
                        self.client.get_client(), args.model, history, args.max_tokens, args.temperature, args.raw
                    )
            else:
                with self.ui.create_progress(transient=not args.raw) as progress:
                    task = progress.add_task("thinking", total=None)
                    response_text = await self.client.send_message(
                        args.model, history, args.max_tokens, args.temperature
                    )

            # Ajouter la réponse à l'historique
            history.append({"role": "assistant", "content": response_text})

            # Afficher la réponse
            if not args.stream:
                self.ui.print_assistant_response(response_text, args.raw)

            # Sauvegarder l'historique si un ID de conversation est spécifié
            if args.conversation_id:
                self.conv_manager.save_conversation_history(args.conversation_id, history)

            # Sauvegarder la réponse dans un fichier si demandé
            if hasattr(args, 'output') and args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(response_text)
                self.ui.print_success(f"Réponse sauvegardée dans le fichier: {args.output}")

            return response_text

        except RateLimitError:
            self.ui.print_error(
                "Limite de taux dépassée. Veuillez réessayer plus tard ou :\n"
                "1. Réduire la fréquence de vos requêtes\n"
                "2. Utiliser un token de plus petite taille (--max-tokens)\n"
                "3. Utiliser un modèle plus léger (--model claude-3-5-haiku-20240307)"
            )
        except APIStatusError as e:
            status_code = getattr(e, "status_code", "inconnu")
            self.ui.print_error(
                f"Erreur API (statut {status_code}): {str(e)}\n"
                f"Suggestions :\n"
                f"- Si code 401/403 : Vérifiez votre clé API\n"
                f"- Si code 404 : Vérifiez le nom du modèle\n"
                f"- Si code 429 : Réduisez la fréquence des requêtes\n"
                f"- Si code 500+ : Problème côté serveur, réessayez plus tard"
            )
        except APIConnectionError:
            self.ui.print_error(
                "Erreur de connexion à l'API. Vérifiez :\n"
                "1. Votre connexion Internet\n"
                "2. La disponibilité du service Anthropic\n"
                "3. Les paramètres de proxy/firewall"
            )
        except APIError as e:
            error_code = getattr(e, "error_code", "")
            message = str(e)

            # Essayer d'extraire des informations utiles de l'erreur
            specific_advice = ""
            if "insufficient_quota" in message.lower() or "quota" in message.lower():
                specific_advice = "Votre quota API est probablement épuisé. Vérifiez votre facturation."
            elif "invalid_api_key" in message.lower():
                specific_advice = "Votre clé API semble invalide. Utilisez '--setup' pour la reconfigurer."
            elif "model" in message.lower() and "not found" in message.lower():
                specific_advice = f"Le modèle spécifié n'existe pas. Utilisez '--models' pour voir les modèles disponibles."

            error_message = f"Erreur API générale: {message}"
            if error_code:
                error_message += f" (Code: {error_code})"
            if specific_advice:
                error_message += f"\n→ {specific_advice}"

            self.ui.print_error(error_message)
        except Exception as e:
            self.ui.print_error(f"Erreur inattendue: {str(e)}")
            if args.debug:
                import traceback
                self.ui.console.print(traceback.format_exc())
