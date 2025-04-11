#!/usr/bin/env bash
# install.sh - Script d'installation pour Ayla CLI (Linux)

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
echo "     Installation de Ayla CLI (Linux)     "
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

# Créer l'environnement d'installation
setup_install_dir() {
    echo -e "\n${YELLOW}Création du répertoire d'installation...${NC}"

    INSTALL_DIR="$HOME/.local/share/ayla_cli"
    mkdir -p "$INSTALL_DIR"

    echo -e "${YELLOW}Copie des fichiers vers $INSTALL_DIR...${NC}"
    cp -r ./* "$INSTALL_DIR"

    echo -e "${GREEN}Fichiers copiés dans $INSTALL_DIR${NC}"
}

# Créer un environnement virtuel
create_venv() {
    echo -e "\n${YELLOW}Création de l'environnement virtuel...${NC}"

    cd "$INSTALL_DIR"
    $PYTHON_CMD -m venv venv || $PYTHON_CMD -m ensurepip && $PYTHON_CMD -m venv venv

    echo -e "${GREEN}Environnement virtuel créé.${NC}"
}

# Installer les dépendances
install_dependencies() {
    echo -e "\n${YELLOW}Installation des dépendances depuis requirements.txt...${NC}"

    VENV_PATH="$INSTALL_DIR/venv"
    PIP_PATH="$VENV_PATH/bin/pip"

    if [ ! -f "$PIP_PATH" ]; then
        echo -e "${RED}Erreur: pip n'a pas été trouvé dans l'environnement virtuel.${NC}"
        echo -e "${YELLOW}Tentative d'installation directe de pip...${NC}"
        $PYTHON_CMD -m ensurepip --upgrade
        cd "$INSTALL_DIR"
        $PYTHON_CMD -m venv venv
    fi

    if [ -f "requirements.txt" ]; then
        "$VENV_PATH/bin/python" -m pip install --upgrade pip
        "$VENV_PATH/bin/python" -m pip install -r requirements.txt
        echo -e "${GREEN}Dépendances installées avec succès.${NC}"
    else
        echo -e "${RED}Erreur: Le fichier requirements.txt n'a pas été trouvé.${NC}"
        echo -e "${YELLOW}Installation des dépendances de base...${NC}"
        "$VENV_PATH/bin/python" -m pip install anthropic rich
        echo -e "${GREEN}Dépendances de base installées.${NC}"
    fi
}

# Configuration de la clé API et de l'alias
setup_environment() {
    echo -e "\n${YELLOW}Configuration de la clé API et de l'alias...${NC}"

    SHELL_TYPE=$(basename "$SHELL")
    case "$SHELL_TYPE" in
        bash) RC_FILE="$HOME/.bashrc" ;;
        zsh) RC_FILE="$HOME/.zshrc" ;;
        fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
        *) RC_FILE="$HOME/.profile" ;;
    esac

    echo -e "${YELLOW}Veuillez entrer votre clé API Anthropic:${NC}"
    read -r API_KEY

    if [ -n "$API_KEY" ]; then
        if grep -q "ANTHROPIC_API_KEY" "$RC_FILE"; then
            echo -e "${YELLOW}Une clé API est déjà configurée. La remplacer ? (o/n)${NC}"
            read -r replace_key
            if [[ "$replace_key" =~ ^([oO][uU][iI]|[oO])$ ]]; then
                sed -i '/export ANTHROPIC_API_KEY/d' "$RC_FILE"
                echo -e "\n# Clé API Anthropic pour Ayla CLI" >> "$RC_FILE"
                echo "export ANTHROPIC_API_KEY=\"$API_KEY\"" >> "$RC_FILE"
                echo -e "${GREEN}Clé API mise à jour.${NC}"
            fi
        else
            echo -e "\n# Clé API Anthropic pour Ayla CLI" >> "$RC_FILE"
            echo "export ANTHROPIC_API_KEY=\"$API_KEY\"" >> "$RC_FILE"
            echo -e "${GREEN}Clé API ajoutée.${NC}"
        fi
    else
        echo -e "${YELLOW}Aucune clé API fournie.${NC}"
    fi
}

# Créer un lien symbolique pour l'exécution globale
create_symlink() {
    echo -e "\n${YELLOW}Configuration de l'accès global à Ayla CLI...${NC}"

    SHELL_TYPE=$(basename "$SHELL")
    case "$SHELL_TYPE" in
        bash) RC_FILE="$HOME/.bashrc" ;;
        zsh) RC_FILE="$HOME/.zshrc" ;;
        fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
        *) RC_FILE="$HOME/.profile" ;;
    esac

    mkdir -p "$HOME/.local/bin"
    WRAPPER_PATH="$HOME/.local/bin/ayla"

    cat > "$WRAPPER_PATH" << EOF
#!/usr/bin/env bash
SCRIPT_DIR="\$HOME/.local/share/ayla_cli"
"\$SCRIPT_DIR/venv/bin/python" "\$SCRIPT_DIR/main.py" "\$@"
EOF

    chmod +x "$WRAPPER_PATH"

    if ! grep -q "alias ayla=" "$RC_FILE" 2>/dev/null; then
        echo 'alias ayla="$HOME/.local/bin/ayla"' >> "$RC_FILE"
        echo -e "${GREEN}Alias 'ayla' ajouté.${NC}"
    fi

    echo -e "${YELLOW}Redémarrez votre terminal ou exécutez:${NC}"
    echo -e "${BLUE}source $RC_FILE${NC}"
    echo -e "${GREEN}Le script 'ayla' est maintenant disponible globalement.${NC}"
}

initial_setup() {
    echo -e "\n${YELLOW}Configuration initiale...${NC}"
    cd "$INSTALL_DIR"
    "./venv/bin/python" main.py --setup
    echo -e "${GREEN}Configuration initiale terminée.${NC}"
}

main() {
    check_python
    setup_install_dir
    create_venv
    install_dependencies
    setup_environment
    create_symlink

    echo -e "\n${GREEN}Installation réussie!${NC}"
    echo -e "${YELLOW}Lancer la configuration initiale maintenant ? (o/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([oO][uU][iI]|[oO])$ ]]; then
        initial_setup
    else
        echo -e "\n${BLUE}Plus tard, exécutez:${NC}"
        echo -e "ayla --setup"
    fi

    echo -e "\n${BLUE}Utilisation:${NC}"
    echo -e "ayla \"Votre question ici\""
    echo -e "ayla -i  # Mode interactif"
    echo -e "${GREEN}Bon chat avec Ayla!${NC}"
}

main
