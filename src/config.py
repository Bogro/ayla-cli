import json
import os
import base64
import hashlib
import sys
import getpass
from typing import Dict, Any, Optional


class ApiKeySecurityManager:
    """Gère la sécurité de la clé API"""
    
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.salt_file = os.path.join(config_dir, ".salt")
        self._ensure_salt()
    
    def _ensure_salt(self):
        """Crée un salt s'il n'existe pas déjà"""
        if not os.path.exists(self.salt_file):
            # Générer un salt aléatoire
            import secrets
            salt = secrets.token_bytes(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            # Appliquer les permissions correctes (lecture/écriture pour le propriétaire uniquement)
            if sys.platform != "win32":
                os.chmod(self.salt_file, 0o600)
    
    def _get_salt(self) -> bytes:
        """Récupère le salt"""
        with open(self.salt_file, 'rb') as f:
            return f.read()
    
    def _derive_key(self) -> bytes:
        """Dérive une clé de chiffrement à partir d'informations système"""
        # Utiliser une combinaison d'informations machine pour dériver une clé
        system_info = []
        # Nom d'utilisateur
        system_info.append(getpass.getuser().encode())
        # Répertoire personnel de l'utilisateur
        system_info.append(os.path.expanduser("~").encode())
        # ID processus parent (pour rendre la clé légèrement plus difficile à deviner)
        system_info.append(str(os.getppid()).encode())
        
        # Utiliser ces informations pour dériver une clé
        concatenated = b"".join(system_info)
        salt = self._get_salt()
        return hashlib.pbkdf2_hmac('sha256', concatenated, salt, 100000, 32)
    
    def encrypt(self, api_key: str) -> str:
        """Chiffre la clé API"""
        if not api_key:
            return ""
            
        key = self._derive_key()
        
        # Simple chiffrement XOR (pour une sécurité basique)
        # Pour une sécurité renforcée, vous pourriez utiliser une bibliothèque comme cryptography
        from itertools import cycle
        encrypted = bytes(a ^ b for a, b in zip(api_key.encode(), cycle(key)))
        
        # Encoder en base64 pour le stockage
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_api_key: str) -> str:
        """Déchiffre la clé API"""
        if not encrypted_api_key:
            return ""
            
        try:
            key = self._derive_key()
            
            # Décoder de base64
            encrypted = base64.b64decode(encrypted_api_key)
            
            # Déchiffrement XOR
            from itertools import cycle
            decrypted = bytes(a ^ b for a, b in zip(encrypted, cycle(key)))
            
            return decrypted.decode()
        except Exception:
            # En cas d'erreur, retourner une chaîne vide
            return ""


class AylaConfig:
    """Gestion de la configuration de l'application"""

    CONFIG_DIR = os.path.expanduser("~/.ayla-cli")
    DEFAULT_ANALYSIS_DIR = os.path.expanduser("~/ayla_analyses")
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
        self.key_manager = ApiKeySecurityManager(self.CONFIG_DIR)

    def setup_directories(self):
        """Crée les répertoires nécessaires s'ils n'existent pas"""
        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        os.makedirs(self.HISTORY_DIR, exist_ok=True)
        
        # Appliquer les bonnes permissions au répertoire de configuration
        if sys.platform != "win32":
            os.chmod(self.CONFIG_DIR, 0o700)  # Droits restreints: lecture/écriture/exécution pour le propriétaire uniquement

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
            
        # Appliquer les bonnes permissions au fichier de configuration
        if sys.platform != "win32":
            os.chmod(self.CONFIG_FILE, 0o600)  # Droits restreints: lecture/écriture pour le propriétaire uniquement

    def get(self, key: str, default=None) -> Any:
        """Récupère une valeur de configuration"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """Définit une valeur de configuration"""
        if key == "api_key" and value:
            # Chiffrer la clé API avant de la stocker
            self._config[key] = self.key_manager.encrypt(value)
        else:
            self._config[key] = value
        self.save_config()

    def get_api_key(self, args) -> str:
        """Récupère la clé API selon la priorité: args > env > config > user input"""
        # Priorité 1 : Argument en ligne de commande
        if args.api_key:
            return args.api_key

        # Priorité 2 : Variable d'environnement
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return api_key

        # Priorité 3: Fichier de configuration (chiffré)
        encrypted_api_key = self.get("api_key")
        if encrypted_api_key:
            return self.key_manager.decrypt(encrypted_api_key)

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
