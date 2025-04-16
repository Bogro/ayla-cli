import json
import os
import time

from src.config.config import AylaConfig


class AuditLogger:
    """Journal d'audit des actions sensibles"""

    def __init__(self, log_file=None):
        self.log_file = log_file or os.path.join(AylaConfig.CONFIG_DIR, "audit.log")

    def log_action(self, action, user=None, success=True, details=None):
        """Enregistre une action dans le journal d'audit"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        username = user or os.getenv('USER') or 'unknown'
        status = "SUCCESS" if success else "FAILED"

        log_entry = {
            "timestamp": timestamp,
            "user": username,
            "action": action,
            "status": status,
            "details": details or {}
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

    def log_api_call(self, model, max_tokens, temperature, prompt_length, success=True, error=None):
        """Enregistre un appel API"""
        details = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "prompt_length": prompt_length
        }

        if not success and error:
            details["error"] = str(error)

        self.log_action("API_CALL", success=success, details=details)

    def log_authentication(self, method, success=True, error=None):
        """Enregistre une tentative d'authentification"""
        details = {"method": method}

        if not success and error:
            details["error"] = str(error)

        self.log_action("AUTHENTICATION", success=success, details=details)

    def log_access(self, resource_type, resource_id, action, success=True, error=None):
        """Enregistre un accès à une ressource"""
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action
        }

        if not success and error:
            details["error"] = str(error)

        self.log_action("RESOURCE_ACCESS", success=success, details=details)