#!/usr/bin/env bash
# install.sh - Script d'installation pour Claude CLI (Linux)

set -e  # Arrêter le script si une commande échoue

# Couleurs pour une meilleure lisibilité
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Bannière d'accueil
echo -e "${BLUE}"
echo "=========================================="
echo "    Installation de Ayla CLI (Linux)     "
echo "=========================================="
echo -e "${NC}"

# Vérifier si Python est installé et sa version
check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        if [[ $(echo "$PYTHON_VERSION" | cut -d. -f1) -ge 3 ]]; then
            PYTHON_CMD="python"
        else
            echo -e "${RED}Erreur: Python 3 est requis mais la version $PYTHON_VERSION a été trouvée.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Erreur: Python 3 n'est pas installé.${NC}"
        echo -e "Veuillez installer Python 3 avec votre gestionnaire de paquets:"
        echo -e "${BLUE}sudo apt install python3 python3-pip python3-venv${NC} (Ubuntu/Debian)"
        echo -e "${BLUE}sudo dnf install python3 python3-pip${NC} (Fedora)"
        exit 1
    fi

    echo -e "${GREEN}Utilisation de $($PYTHON_CMD --version)${NC}"
}

# Créer un environnement virtuel
create_venv() {
    echo -e "\n${YELLOW}Création de l'environnement virtuel...${NC}"

    # Détecter si nous sommes dans un répertoire git
    if [ -d ".git" ]; then
        INSTALL_DIR="$(pwd)"
    else
        # Créer un répertoire dans le dossier utilisateur
        INSTALL_DIR="$HOME/.ayla-cli"
        mkdir -p "$INSTALL_DIR"

        # Copier les fichiers source dans le répertoire d'installation
        echo -e "${YELLOW}Copie des fichiers vers $INSTALL_DIR...${NC}"
        cp -r * "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    $PYTHON_CMD -m venv venv
    source venv/bin/activate

    echo -e "${GREEN}Environnement virtuel créé et activé.${NC}"
}

# Installer les dépendances
install_dependencies() {
    echo -e "\n${YELLOW}Installation des dépendances depuis requirements.txt...${NC}"
    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip
        pip install -r requirements.txt
        echo -e "${GREEN}Dépendances installées avec succès.${NC}"
    else
        echo -e "${RED}Erreur: Le fichier requirements.txt n'a pas été trouvé.${NC}"
        echo -e "${YELLOW}Installation des dépendances de base...${NC}"
        pip install anthropic rich
        echo -e "${GREEN}Dépendances de base installées.${NC}"
    fi
}

# Configuration de la clé API et de l'alias
setup_environment() {
    echo -e "\n${YELLOW}Configuration de la clé API et de l'alias...${NC}"

    # Détecter le shell de l'utilisateur
    SHELL_TYPE=$(basename "$SHELL")
    RC_FILE=""

    case "$SHELL_TYPE" in
        bash)   RC_FILE="$HOME/.bashrc" ;;
        zsh)    RC_FILE="$HOME/.zshrc" ;;
        fish)   RC_FILE="$HOME/.config/fish/config.fish" ;;
        *)      RC_FILE="$HOME/.profile" ;;
    esac

    # Demander la clé API
    echo -e "${YELLOW}Veuillez entrer votre clé API Anthropic:${NC}"
    read -r API_KEY

    if [ -n "$API_KEY" ]; then
        # Vérifier si la clé API est déjà configurée
        if grep -q "ANTHROPIC_API_KEY" "$RC_FILE"; then
            echo -e "${YELLOW}Une clé API Anthropic est déjà configurée dans $RC_FILE.${NC}"
            echo -e "${YELLOW}Souhaitez-vous la remplacer? (o/n)${NC}"
            read -r replace_key

            if [[ "$replace_key" =~ ^([oO][uU][iI]|[oO])$ ]]; then
                # Supprimer l'ancienne configuration
                sed -i '/export ANTHROPIC_API_KEY/d' "$RC_FILE"
                # Ajouter la nouvelle clé
                echo -e "\n# Clé API Anthropic pour Ayla CLI" >> "$RC_FILE"
                echo "export ANTHROPIC_API_KEY=\"$API_KEY\"" >> "$RC_FILE"
                echo -e "${GREEN}Clé API mise à jour dans $RC_FILE${NC}"
            fi
        else
            # Ajouter la clé API au fichier de configuration
            echo -e "\n# Clé API Anthropic pour Ayla CLI" >> "$RC_FILE"
            echo "export ANTHROPIC_API_KEY=\"$API_KEY\"" >> "$RC_FILE"
            echo -e "${GREEN}Clé API ajoutée à $RC_FILE${NC}"
        fi
    else
        echo -e "${YELLOW}Aucune clé API fournie. Vous devrez configurer la variable ANTHROPIC_API_KEY manuellement.${NC}"
    fi
}

# Créer un lien symbolique pour l'exécution globale
create_symlink() {
    echo -e "\n${YELLOW}Configuration de l'accès global à Ayla CLI...${NC}"

    # Détecter le shell de l'utilisateur
    SHELL_TYPE=$(basename "$SHELL")
    RC_FILE=""

    case "$SHELL_TYPE" in
        bash)   RC_FILE="$HOME/.bashrc" ;;
        zsh)    RC_FILE="$HOME/.zshrc" ;;
        fish)   RC_FILE="$HOME/.config/fish/config.fish" ;;
        *)      RC_FILE="$HOME/.profile" ;;
    esac

    # Créer le script d'enveloppe dans ~/bin
    mkdir -p "$HOME/bin"
    WRAPPER_PATH="$HOME/bin/main.py"

    cat > "$WRAPPER_PATH" << EOF
#!/usr/bin/env bash
# Script d'enveloppe pour Claude CLI
source "$INSTALL_DIR/venv/bin/activate"
$PYTHON_CMD "$INSTALL_DIR/main.py" "\$@"
EOF

    chmod +x "$WRAPPER_PATH"

    # Ajouter ~/bin au PATH si ce n'est pas déjà fait
    if ! grep -q 'PATH="$HOME/bin:$PATH"' "$RC_FILE" 2>/dev/null; then
        echo -e "\n# Ajouté par l'installateur Ayla CLI" >> "$RC_FILE"
        echo 'export PATH="$HOME/bin:$PATH"' >> "$RC_FILE"
        echo -e "${GREEN}$HOME/bin ajouté à votre PATH dans $RC_FILE${NC}"
    fi

    # Ajouter l'alias
    if ! grep -q "alias ayla=" "$RC_FILE" 2>/dev/null; then
        echo -e "\n# Alias pour Ayla CLI" >> "$RC_FILE"
        echo 'alias ayla="~/bin/main.py"' >> "$RC_FILE"
        echo -e "${GREEN}Alias 'aila' ajouté à $RC_FILE${NC}"
    fi

    echo -e "${YELLOW}Pour appliquer ces changements, redémarrez votre terminal ou exécutez:${NC}"
    echo -e "${BLUE}source $RC_FILE${NC}"

    echo -e "${GREEN}Le script est maintenant disponible globalement via la commande 'ayla'.${NC}"
}

# Configuration initiale
initial_setup() {
    echo -e "\n${YELLOW}Configuration initiale de Ayla CLI...${NC}"

    # Exécuter la configuration automatique
    $PYTHON_CMD main.py --setup

    echo -e "${GREEN}Configuration initiale terminée.${NC}"
}

# Exécution principale
main() {
    check_python
    create_venv
    install_dependencies
    setup_environment
    create_symlink

    echo -e "\n${GREEN}Installation de Ayla CLI terminée avec succès!${NC}"
    echo -e "${YELLOW}Souhaitez-vous lancer la configuration initiale maintenant? (o/n)${NC}"
    read -r response

    if [[ "$response" =~ ^([oO][uU][iI]|[oO])$ ]]; then
        source "$RC_FILE"  # Charger la configuration avec la clé API
        initial_setup
    else
        echo -e "\n${BLUE}Pour configurer Ayla CLI plus tard, exécutez:${NC}"
        echo -e "ayla --setup"
    fi

    echo -e "\n${BLUE}Pour commencer à utiliser Ayla CLI, exécutez:${NC}"
    echo -e "ayla \"Votre question ici\""
    echo -e "ayla -i  # Mode interactif"
    echo -e "${GREEN}Bon chat avec Ayla CLI!${NC}"
}

main