# Ayla CLI

Une interface en ligne de commande avancé, vous permettant d'interagir avec les modèles Claude d'Anthropic directement depuis votre terminal.

![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.6%2B-brightgreen)

## Caractéristiques

- **Conversations interactives** avec historique et gestion de sessions
- **Formatage riche** du texte et des blocs de code avec coloration syntaxique
- **Gestion des conversations** pour sauvegarder, charger et reprendre vos échanges
- **Templates de prompts** réutilisables pour des interactions standardisées
- **Recherche** dans votre historique de conversations
- **Bibliothèque de modèles** avec accès à Claude 3 Opus, Claude 3.7 Sonnet, Claude 3.5 Haiku, etc.
- **Traitement de fichiers** pour inclure le contenu de fichiers dans vos prompts
- **Mode debug** pour les développeurs

## Installation

### Prérequis

- Python 3.6 ou supérieur
- Une clé API Anthropic valide

### Installation rapide

Cloner le répertoire
```bash
git clone https://github.com/bogro/ayla-cli.git && cd ayla-cli
```

Rendez le script exécutable
```bash
chmod +x install.sh
```

Exécutez-le
```bash
./install.sh
```

Les dépendances nécessaires (`anthropic` et `rich`) seront installées automatiquement lors de la première utilisation si elles ne sont pas présentes.

## Configuration

Lors de la première utilisation, vous serez invité à configurer votre clé API :

```bash
./main.py --setup
```

Alternativement, vous pouvez :
- Définir la variable d'environnement `ANTHROPIC_API_KEY`
- Passer la clé en argument avec `--api-key`

## Utilisation basique

### Demandes simples

```bash
# Pose une question simple
ayla "Quelle est la capitale du Canada?"

# Analyser un fichier
ayla -f code.py "Explique ce que fait ce code"

# Utiliser l'entrée standard
cat document.txt | ayla "Résume ce texte"
```

### Mode interactif

```bash
# Lancer une nouvelle conversation interactive
ayla -i

# Continuer une conversation existante
ayla -c <ID_CONVERSATION>

# Continuer la conversation la plus récente
ayla --continue
```

### Gestion des conversations

```bash
# Lister toutes les conversations sauvegardées
ayla --list

# Rechercher dans vos conversations
ayla --search "intelligence artificielle"
```

## Commandes du mode interactif

En mode interactif, vous pouvez utiliser les commandes suivantes :

| Commande | Description |
|----------|-------------|
| `/help` ou `/?` | Affiche l'aide du mode interactif |
| `/exit` ou `/quit` ou `/q` | Quitte le mode interactif |
| `/history` | Affiche l'historique complet de la conversation |
| `/clear` | Efface l'historique de la conversation actuelle |
| `/save <id>` | Sauvegarde la conversation avec un ID spécifique |
| `/load <id>` | Charge une conversation existante |
| `/list` | Liste toutes les conversations sauvegardées |
| `/search <terme>` | Recherche dans vos conversations |
| `/tag <tag>` | Ajoute un tag à la conversation actuelle |
| `/export` | Exporte la conversation dans un fichier Markdown |
| `/template <nom>` | Charge un template de prompt |
| `/save_template <nom> <contenu>` | Sauvegarde un nouveau template |
| `/models` | Affiche la liste des modèles disponibles |

## Options avancées

```bash
# Utiliser un modèle spécifique
ayla -m claude-3-opus-20240229 "Explique-moi la théorie de la relativité"

# Ajuster la température (créativité)
ayla -T 0.9 "Écris une histoire courte sur un robot"

# Définir le nombre maximum de tokens
ayla -t 8000 "Résume ce livre chapitre par chapitre"

# Utiliser un template prédéfini
ayla --template code_review -f pull_request.diff

# Sauvegarder la réponse dans un fichier
ayla --output resume.md "Résume cet article scientifique"

# Mode debug pour diagnostiquer les problèmes
ayla -d "Pourquoi la réponse ne s'affiche pas correctement?"

# Augmenter le timeout pour les requêtes complexes
ayla --timeout 180 "Analyse détaillée de ce texte très long"
```

## Dépannage

### Problèmes courants

1. **Erreur d'authentification**: Vérifiez que votre clé API est valide et correctement configurée
2. **Problèmes de streaming**: Utilisez l'option `--debug` pour diagnostiquer
3. **Timeout**: Augmentez la valeur de timeout avec `--timeout`
4. **Erreurs d'encodage de fichiers**: Le CLI essaiera automatiquement différents encodages

## Développement

Contributions et suggestions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## Licence

MIT

## Remerciements

- [Anthropic](https://www.anthropic.com/) pour l'API Claude
- [Rich](https://github.com/Textualize/rich) pour le formatage riche dans le terminal
