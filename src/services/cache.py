import hashlib
import json
import os
import time

from src.config.config import AylaConfig


class ResponseCache:
    """Système de cache pour les réponses de Ayla"""

    def __init__(self, cache_dir=None, ttl=86400):  # 24h par défaut
        self.cache_dir = cache_dir or os.path.join(AylaConfig.CONFIG_DIR, "cache")
        self.ttl = ttl
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(self, model, prompt, temperature):
        """Génère une clé de cache unique basée sur les paramètres de la requête"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        return f"{model}_{prompt_hash}_{temperature}"

    def get(self, model, prompt, temperature):
        """Récupère une réponse depuis le cache si disponible et non expirée"""
        key = self._get_cache_key(model, prompt, temperature)
        cache_file = os.path.join(self.cache_dir, key)

        if os.path.exists(cache_file):
            # Vérifier si le cache a expiré
            mod_time = os.path.getmtime(cache_file)
            if time.time() - mod_time < self.ttl:
                try:
                    with open(cache_file, 'r') as f:
                        return json.load(f)
                except:
                    return None
        return None

    def set(self, model, prompt, temperature, response):
        """Stocke une réponse dans le cache"""
        key = self._get_cache_key(model, prompt, temperature)
        cache_file = os.path.join(self.cache_dir, key)

        with open(cache_file, 'w') as f:
            json.dump(response, f)