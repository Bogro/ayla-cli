import json
import os
from typing import Dict, Any


class AylaConfig:
    """Gestion de la configuration de l'application"""

    CONFIG_DIR = os.path.expanduser("~/.bocode-cli")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
    HISTORY_DIR = os.path.join(CONFIG_DIR, "history")

    # Modèles disponibles avec leurs descriptions
    AVAILABLE_MODELS = {
        "claude-3-7-sonnet-20250219": "Meilleur équilibre entre capacités et vitesse",
        "claude-3-5-sonnet-20240620": "Version antérieure de Claude 3.5 Sonnet",
        "claude-3-opus-20240229": "Le plus puissant pour les tâches complexes",
        "claude-3-5-haiku-20240307": "Le plus rapide pour les tâches simples",
    }

    DEFAULT_MODEL = "claude-3-7-sonnet-20250219"
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TEMPERATURE = 0.7

    def __init__(self):
        """Initialise la configuration"""
        self.setup_directories()
        self._config = self.load_config()

    def setup_directories(self):
        """Crée les répertoires nécessaires s'ils n'existent pas"""
        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        os.makedirs(self.HISTORY_DIR, exist_ok=True)

    def load_config(self) -> Dict:
        """Charge la configuration depuis le fichier config.json"""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Erreur de lecture du fichier de configuration.")
                return {}
        return {}

    def save_config(self):
        """Sauvegarde la configuration dans le fichier config.json"""
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default=None) -> Any:
        """Récupère une valeur de configuration"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """Définit une valeur de configuration"""
        self._config[key] = value
        self.save_config()

    def get_api_key(self, args) -> str:
        """Récupère la clé API selon la priorité: args > env > config > user input"""
        # Priorité 1: Argument en ligne de commande
        if args.api_key:
            return args.api_key

        # Priorité 2: Variable d'environnement
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return api_key

        # Priorité 3: Fichier de configuration
        api_key = self.get("api_key")
        if api_key:
            return api_key

        return ""  # Empty string if not found

    def get_model(self) -> str:
        """Récupère le modèle à utiliser"""
        return self.get("default_model", self.DEFAULT_MODEL)

    def get_max_tokens(self) -> int:
        """Récupère le nombre maximal de tokens à générer"""
        return self.get("default_max_tokens", self.DEFAULT_MAX_TOKENS)

    def get_temperature(self) -> float:
        """Récupère la température à utiliser"""
        return self.get("default_temperature", self.DEFAULT_TEMPERATURE)

    def get_stream(self) -> bool:
        """Récupère la préférence de streaming"""
        return self.get("default_stream", False)
