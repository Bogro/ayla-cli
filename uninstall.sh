#!/usr/bin/env bash
# uninstall.sh - Script de désinstallation pour Ayla CLI (Linux)

set -e

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="$HOME/.local/share/ayla_cli"
WRAPPER_PATH="$HOME/.local/bin/ayla"

echo -e "${BLUE}"
echo "=========================================="
echo "     Désinstallation de Ayla CLI          "
echo "=========================================="
echo -e "${NC}"

# Supprimer le dossier d'installation
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Suppression du répertoire d'installation...${NC}"
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}Répertoire $INSTALL_DIR supprimé.${NC}"
else
    echo -e "${YELLOW}Le répertoire $INSTALL_DIR n'existe pas.${NC}"
fi

# Supprimer le script wrapper
if [ -f "$WRAPPER_PATH" ]; then
    echo -e "${YELLOW}Suppression du binaire global ayla...${NC}"
    rm -f "$WRAPPER_PATH"
    echo -e "${GREEN}Binaire supprimé de $WRAPPER_PATH.${NC}"
fi

# Nettoyer les fichiers de configuration shell
cleanup_shell_config() {
    local RC_FILE="$1"

    if [ -f "$RC_FILE" ]; then
        sed -i '/# Clé API Anthropic pour Ayla CLI/d' "$RC_FILE"
        sed -i '/export ANTHROPIC_API_KEY/d' "$RC_FILE"
        sed -i '/# Alias pour Ayla CLI/d' "$RC_FILE"
        sed -i '/alias ayla=/d' "$RC_FILE"
        sed -i '/# Ajouté par l.*installateur Ayla CLI/d' "$RC_FILE"
        sed -i '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' "$RC_FILE"
        echo -e "${GREEN}Nettoyage effectué dans $RC_FILE.${NC}"
    fi
}

echo -e "${YELLOW}Nettoyage des fichiers de configuration shell...${NC}"
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.config/fish/config.fish"; do
    cleanup_shell_config "$rc"
done

echo -e "\n${GREEN}Ayla CLI a été désinstallé avec succès.${NC}"
echo -e "${YELLOW}Pensez à redémarrer votre terminal ou exécuter:${NC} ${BLUE}source ~/.bashrc${NC} (ou équivalent)"
