"""
Module de routage pour l'application CLI
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Tuple


@dataclass(frozen=True)
class Route:
    """Classe représentant une route dans l'application"""
    command: str
    handler: Callable
    description: str
    subcommands: Dict[str, 'Route'] = None
    aliases: List[str] = None
    help_text: str = ""
    category: str = "general"
    
    def __post_init__(self):
        # Comme la classe est frozen, on doit utiliser object.__setattr__
        if self.subcommands is None:
            object.__setattr__(self, 'subcommands', {})
        if self.aliases is None:
            object.__setattr__(self, 'aliases', [])

    def __hash__(self):
        return hash((self.command, self.description))

    def __eq__(self, other):
        if not isinstance(other, Route):
            return NotImplemented
        return (
            self.command == other.command and 
            self.description == other.description
        )
        
    async def execute(self, *args, **kwargs) -> Tuple[bool, Any]:
        """
        Exécute le handler de la route avec les arguments fournis
        
        Returns:
            Tuple[bool, Any]: (succès, résultat)
                - succès: True si l'exécution s'est bien passée
                - résultat: Le résultat du handler ou le message d'erreur
        """
        try:
            result = await self.handler(*args, **kwargs)
            return True, result
        except Exception as e:
            return False, str(e)

    def get_help(self) -> str:
        """Retourne l'aide détaillée de la commande"""
        help_text = [
            f"Commande: {self.command}",
            f"Description: {self.description}",
        ]
        
        if self.aliases:
            help_text.append(f"Alias: {', '.join(self.aliases)}")
            
        if self.help_text:
            help_text.append(f"\n{self.help_text}")
            
        if self.subcommands:
            help_text.append("\nSous-commandes disponibles:")
            for subcmd in self.subcommands.values():
                if subcmd.command not in subcmd.aliases:
                    help_text.append(f"  {subcmd.command}: {subcmd.description}")
                    
        return "\n".join(help_text)


class Router:
    """Gestionnaire de routes pour l'application CLI"""
    def __init__(self):
        self.routes: Dict[str, Route] = {}
        self.categories: Dict[str, List[Route]] = {}

    def add_route(
        self, command: str, handler: Callable, description: str,
        aliases: List[str] = None, help_text: str = "", category: str = "general"
    ) -> Route:
        """Ajoute une nouvelle route"""
        route = Route(
            command=command,
            handler=handler,
            description=description,
            aliases=aliases,
            help_text=help_text,
            category=category
        )
        self.routes[command] = route
        
        # Ajouter la route à sa catégorie
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(route)
        
        if aliases:
            for alias in aliases:
                self.routes[alias] = route
        return route

    def add_subroute(
        self, parent_command: str, command: str, handler: Callable,
        description: str, aliases: List[str] = None, help_text: str = ""
    ) -> Optional[Route]:
        """Ajoute une sous-route à une commande existante"""
        parent_route = self.routes.get(parent_command)
        if not parent_route:
            return None

        subroute = Route(
            command=command,
            handler=handler,
            description=description,
            aliases=aliases,
            help_text=help_text,
            category=parent_route.category
        )
        parent_route.subcommands[command] = subroute
        if aliases:
            for alias in aliases:
                parent_route.subcommands[alias] = subroute
        return subroute

    async def dispatch(self, command: str, *args, **kwargs) -> Tuple[bool, Any]:
        """
        Dispatch une commande vers son handler approprié
        
        Returns :
            Tuple[bool, Any] : (succès, résultat)
        """
        parts = command.split()
        main_command = parts[0]
        
        if main_command not in self.routes:
            return False, f"Commande inconnue: {main_command}"

        route = self.routes[main_command]
        
        if len(parts) > 1 and parts[1] in route.subcommands:
            subroute = route.subcommands[parts[1]]
            return await subroute.execute(*args, **kwargs)
        
        return await route.execute(*args, **kwargs)

    def get_commands(self) -> Dict[str, str]:
        """Retourne un dictionnaire des commandes et leurs descriptions"""
        commands = {}
        # Utiliser un dictionnaire pour éliminer les doublons
        unique_routes = {
            route.command: route for route in self.routes.values()
        }.values()
        
        for route in unique_routes:
            commands[route.command] = route.description
            for subcmd, subroute in route.subcommands.items():
                if subcmd not in route.aliases:  # Éviter les alias
                    cmd_key = f"{route.command} {subcmd}"
                    commands[cmd_key] = subroute.description
        return commands
        
    def get_commands_by_category(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Retourne les commandes groupées par catégorie avec des informations détaillées
        
        Returns :
            Dict[str, List[Dict[str, str]]] : Dictionnaire avec :
                - clé : nom de la catégorie
                - valeur : liste de commandes avec leurs détails
                  {
                      'command' : str, # Nom de la commande
                      'description' : str, # Description courte
                      'help' : str, # Aide détaillée
                      'aliases' : List[str], # Liste des alias
                      'subcommands' : List[Dict[str, str]] # Sous-commandes
                  }
        """
        result = {}
        
        # Initialiser toutes les catégories
        for category in set(route.category for route in self.routes.values()):
            result[category] = []
            
        # Regrouper les routes par catégorie
        for route in self.routes.values():
            # Éviter les doublons dus aux alias
            if route.command in route.aliases:
                continue
                
            # Préparer les informations de la commande
            command_info = {
                'command': route.command,
                'description': route.description,
                'help': route.help_text,
                'aliases': route.aliases,
                'subcommands': []
            }
            
            # Ajouter les sous-commandes si présentes
            for subcmd, subroute in route.subcommands.items():
                # Éviter les alias dans les sous-commandes
                if subcmd not in subroute.aliases:
                    subcommand_info = {
                        'command': f"{route.command} {subcmd}",
                        'name': subcmd,
                        'description': subroute.description,
                        'help': subroute.help_text,
                        'aliases': subroute.aliases
                    }
                    command_info['subcommands'].append(subcommand_info)
            
            # Ajouter la commande à sa catégorie
            result[route.category].append(command_info)
            
        # Trier les commandes par nom dans chaque catégorie
        for category in result:
            result[category].sort(key=lambda x: x['command'])
            
            # Trier les sous-commandes
            for cmd in result[category]:
                cmd['subcommands'].sort(key=lambda x: x['command'])
                
        return result 