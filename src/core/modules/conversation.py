import json
import os
import time
from typing import List, Dict, Optional

from src.config.config import AylaConfig
from src.core.ui import UI


class ConversationManager:
    """Gestion des conversations et de leur historique"""

    def __init__(self, config: AylaConfig, ui: UI):
        """Initialise le gestionnaire de conversations"""
        self.config = config
        self.ui = ui
        self.history_dir = config.HISTORY_DIR

    def load_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Charge l'historique d'une conversation spécifique"""
        history_file = os.path.join(self.history_dir, f"{conversation_id}.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.ui.print_warning(
                    f"Erreur lors de la lecture de l'historique. Démarrage d'une nouvelle conversation.")
        return []

    def save_conversation_history(self, conversation_id: str, history: List[Dict[str, str]]):
        """Sauvegarde l'historique d'une conversation"""
        history_file = os.path.join(self.history_dir, f"{conversation_id}.json")
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

    def list_conversations(self) -> List[Dict]:
        """Liste toutes les conversations sauvegardées"""
        conversations = []
        for filename in os.listdir(self.history_dir):
            if filename.endswith('.json'):
                conversation_id = filename[:-5]  # Enlever l'extension .json
                history_file = os.path.join(self.history_dir, filename)

                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                        # Extraire la première question de l'utilisateur pour l'afficher comme titre
                        title = "Conversation sans titre"
                        for message in history:
                            if message["role"] == "user":
                                title = message["content"][:50] + ('...' if len(message["content"]) > 50 else '')
                                break

                        # Calculer la date de dernière modification
                        mod_time = os.path.getmtime(history_file)
                        mod_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))

                        conversations.append({
                            "id": conversation_id,
                            "title": title,
                            "messages": len(history),
                            "last_modified": mod_date
                        })
                except (json.JSONDecodeError, KeyError):
                    self.ui.print_warning(f"Erreur lors de la lecture du fichier {filename}")

        return sorted(conversations, key=lambda x: x["last_modified"], reverse=True)

    def get_latest_conversation_id(self) -> Optional[str]:
        """Récupère l'ID de la conversation la plus récente"""
        conversations = self.list_conversations()
        if conversations:
            return conversations[0]["id"]
        return None
