
class CommandCompleter:
    """Système d'autocomplétion pour le mode interactif"""

    def __init__(self, conv_manager):
        self.commands = [
            '/exit', '/quit', '/q', '/help', '/?',
            '/history', '/save', '/clear', '/list', '/load'
        ]
        self.conv_manager = conv_manager

    def complete(self, text, state):
        """Fonction d'autocomplétion pour readline"""
        # Compléter les commandes
        if text.startswith('/'):
            matches = [cmd for cmd in self.commands if cmd.startswith(text)]

            # Autocomplétion spéciale pour /load et /save
            if text.startswith('/load ') or text.startswith('/save '):
                cmd_parts = text.split(' ', 1)
                if len(cmd_parts) > 1 and cmd_parts[0] == '/load':
                    conv_id_prefix = cmd_parts[1]
                    conversations = self.conv_manager.list_conversations()
                    matches = [f"/load {conv['id']}" for conv in conversations
                               if conv['id'].startswith(conv_id_prefix)]

            if state < len(matches):
                return matches[state]
        return None