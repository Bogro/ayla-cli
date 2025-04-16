import os
import subprocess
from typing import Dict, List, Optional, Tuple, Any
import re
import time

from src.views.ui import UI


class GitManager:
    """Gestionnaire intelligent de versionnage Git"""

    def __init__(self, ui: UI):
        """Initialise le gestionnaire de versionnage Git"""
        self.ui = ui
        self.repo_path = None
        self.is_git_repo = False
        self.current_branch = None
        self.last_check = 0
        self.repo_info = {}

    def set_repo_path(self, path: str) -> bool:
        """Définit le chemin du dépôt Git et vérifie s'il s'agit d'un dépôt valide"""
        if not os.path.isdir(path):
            self.ui.print_error(f"Le chemin {path} n'est pas un répertoire valide")
            return False

        self.repo_path = path
        self.is_git_repo = self._is_git_repository()

        if self.is_git_repo:
            self.current_branch = self._get_current_branch()
            self.refresh_repo_info()
            return True
        else:
            self.ui.print_warning(f"Le répertoire {path} n'est pas un dépôt Git valide")
            return False

    def _is_git_repository(self) -> bool:
        """Vérifie si le répertoire est un dépôt Git valide"""
        git_dir = os.path.join(self.repo_path, '.git')
        return os.path.isdir(git_dir)

    def _run_git_command(self, command: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
        """Exécute une commande Git et retourne le résultat"""
        try:
            working_dir = cwd if cwd else self.repo_path
            result = subprocess.run(
                ['git'] + command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def refresh_repo_info(self) -> Dict[str, Any]:
        """Rafraîchit les informations du dépôt Git"""
        if not self.is_git_repo:
            return {}

        # Limiter la fréquence des rafraîchissements (max 1 fois par seconde)
        current_time = time.time()
        if current_time - self.last_check < 1.0 and self.repo_info:
            return self.repo_info

        self.last_check = current_time
        self.repo_info = {
            'branch': self._get_current_branch(),
            'status': self._get_repo_status(),
            'last_commit': self._get_last_commit(),
            'branches': self._get_branches(),
            'remotes': self._get_remotes(),
            'stashes': self._get_stashes()
        }

        return self.repo_info

    def _get_current_branch(self) -> str:
        """Obtient la branche actuelle"""
        success, output = self._run_git_command(['branch', '--show-current'])
        return output if success else "unknown"

    def _get_repo_status(self) -> Dict[str, Any]:
        """Obtient le statut du dépôt"""
        success, output = self._run_git_command(['status', '--porcelain'])

        status = {
            'is_clean': not output,
            'modified': [],
            'untracked': [],
            'staged': [],
            'raw': output
        }

        if not success:
            return status

        for line in output.split('\n'):
            if not line:
                continue

            status_code = line[:2]
            file_path = line[3:]

            if status_code[0] == '?':
                status['untracked'].append(file_path)
            elif status_code[0] in 'MADRCU':
                status['staged'].append(file_path)
            if status_code[1] in 'MADRCU':
                status['modified'].append(file_path)

        return status

    def _get_last_commit(self) -> Dict[str, str]:
        """Obtient les informations sur le dernier commit"""
        success, output = self._run_git_command(['log', '-1', '--pretty=format:%h|%an|%ad|%s'])

        if not success or not output:
            return {'hash': '', 'author': '', 'date': '', 'message': ''}

        parts = output.split('|', 3)
        if len(parts) != 4:
            return {'hash': '', 'author': '', 'date': '', 'message': ''}

        return {
            'hash': parts[0],
            'author': parts[1],
            'date': parts[2],
            'message': parts[3]
        }

    def _get_branches(self) -> List[str]:
        """Obtient la liste des branches"""
        success, output = self._run_git_command(['branch'])

        if not success:
            return []

        branches = []
        for line in output.split('\n'):
            if line.strip():
                # Enlever l'astérisque et les espaces de début
                branches.append(re.sub(r'^\*?\s*', '', line))

        return branches

    def _get_remotes(self) -> Dict[str, str]:
        """Obtient la liste des remotes"""
        success, output = self._run_git_command(['remote', '-v'])

        if not success:
            return {}

        remotes = {}
        for line in output.split('\n'):
            if not line:
                continue

            parts = line.split()
            if len(parts) >= 2 and '(fetch)' in line:
                remotes[parts[0]] = parts[1]

        return remotes

    def _get_stashes(self) -> List[Dict[str, str]]:
        """Obtient la liste des stashes"""
        success, output = self._run_git_command(['stash', 'list'])

        if not success:
            return []

        stashes = []
        for line in output.split('\n'):
            if not line:
                continue

            match = re.match(r'stash@\{(\d+)\}: (.*)', line)
            if match:
                stashes.append({
                    'index': match.group(1),
                    'description': match.group(2)
                })

        return stashes

    def commit_changes(self, message: str, files: Optional[List[str]] = None) -> bool:
        """Crée un commit avec les changements"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        # Vérifier s'il y a des changements
        status = self._get_repo_status()
        if status['is_clean']:
            self.ui.print_warning("Aucun changement à commiter")
            return False

        # Ajouter les fichiers spécifiques ou tous les fichiers modifiés
        if files:
            for file in files:
                success, output = self._run_git_command(['add', file])
                if not success:
                    self.ui.print_error(f"Erreur lors de l'ajout du fichier {file}: {output}")
                    return False
        else:
            success, output = self._run_git_command(['add', '.'])
            if not success:
                self.ui.print_error(f"Erreur lors de l'ajout des fichiers: {output}")
                return False

        # Créer le commit
        success, output = self._run_git_command(['commit', '-m', message])

        if success:
            self.ui.print_success(f"Commit créé avec succès: {output}")
            self.refresh_repo_info()
            return True
        else:
            self.ui.print_error(f"Erreur lors de la création du commit: {output}")
            return False

    def switch_branch(self, branch_name: str, create: bool = False) -> bool:
        """Change de branche ou en crée une nouvelle"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        command = ['checkout']
        if create:
            command.append('-b')
        command.append(branch_name)

        success, output = self._run_git_command(command)

        if success:
            self.current_branch = branch_name
            self.refresh_repo_info()
            self.ui.print_success(f"Branche changée pour {branch_name}")
            return True
        else:
            self.ui.print_error(f"Erreur lors du changement de branche: {output}")
            return False

    def push_changes(self, remote: str = 'origin', branch: Optional[str] = None) -> bool:
        """Pousse les changements vers le remote"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        target_branch = branch if branch else self.current_branch
        command = ['push', remote, target_branch]

        success, output = self._run_git_command(command)

        if success:
            self.ui.print_success(f"Changements poussés vers {remote}/{target_branch}")
            return True
        else:
            self.ui.print_error(f"Erreur lors du push: {output}")
            return False

    def pull_changes(self, remote: str = 'origin', branch: Optional[str] = None) -> bool:
        """Tire les changements depuis le remote"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        target_branch = branch if branch else self.current_branch
        command = ['pull', remote, target_branch]

        success, output = self._run_git_command(command)

        if success:
            self.refresh_repo_info()
            self.ui.print_success(f"Changements tirés depuis {remote}/{target_branch}")
            return True
        else:
            self.ui.print_error(f"Erreur lors du pull: {output}")
            return False

    def get_detailed_diff(self, file_path: Optional[str] = None) -> str:
        """Obtient le diff détaillé pour un fichier ou pour tout le dépôt"""
        if not self.is_git_repo:
            return "Vous n'êtes pas dans un dépôt Git valide"

        command = ['diff', '--color=never']
        if file_path:
            command.append(file_path)

        success, output = self._run_git_command(command)

        if success:
            return output if output else "Aucune différence détectée"
        else:
            return f"Erreur lors de la récupération du diff: {output}"

    def get_commit_history(self, count: int = 10) -> List[Dict[str, str]]:
        """Obtient l'historique des commits"""
        if not self.is_git_repo:
            return []

        command = ['log', f'-{count}', '--pretty=format:%h|%an|%ad|%s']
        success, output = self._run_git_command(command)

        if not success:
            return []

        commits = []
        for line in output.split('\n'):
            if not line:
                continue

            parts = line.split('|', 3)
            if len(parts) == 4:
                commits.append({
                    'hash': parts[0],
                    'author': parts[1],
                    'date': parts[2],
                    'message': parts[3]
                })

        return commits

    def generate_commit_message(self, diff_text: str) -> str:
        """Génère un message de commit intelligent basé sur les modifications"""
        # Cette méthode sera remplacée par un appel à Claude
        # Pour l'instant, une implémentation simple
        if not diff_text:
            return "Mise à jour du code"

        changed_files = []
        for line in diff_text.split('\n'):
            if line.startswith('diff --git'):
                file_path = line.split(' b/')[-1]
                changed_files.append(os.path.basename(file_path))

        if len(changed_files) == 1:
            return f"Modification de {changed_files[0]}"
        else:
            return f"Modifications dans {len(changed_files)} fichiers: " + ", ".join(changed_files[:3]) + \
                (" et d'autres" if len(changed_files) > 3 else "")

    def suggest_branch_name(self, task_description: str) -> str:
        """Suggère un nom de branche basé sur la description de la tâche"""
        # Cette méthode sera remplacée par un appel à Claude
        # Pour l'instant, une implémentation simple
        words = re.findall(r'\w+', task_description.lower())
        if not words:
            return f"feature-{int(time.time())}"

        # Prendre les 3 premiers mots significatifs (au moins 3 lettres)
        feature_words = [word for word in words if len(word) >= 3][:3]

        if not feature_words:
            return f"feature-{int(time.time())}"

        return "feature-" + "-".join(feature_words)

    def analyze_repo(self) -> Dict[str, Any]:
        """Analyse le dépôt Git et fournit des insights"""
        if not self.is_git_repo:
            return {"error": "Pas de dépôt Git valide"}

        # Rafraîchir les informations
        self.refresh_repo_info()

        # Obtenir l'historique des commits
        commits = self.get_commit_history(20)

        # Calculer des statistiques de base
        authors = {}
        commit_frequency = {}

        for commit in commits:
            # Compter les commits par auteur
            author = commit['author']
            authors[author] = authors.get(author, 0) + 1

            # Extraire la date
            date_str = commit['date']
            try:
                # Supposons que le format est standard Git
                # Extraire juste la date (pas l'heure)
                date_parts = date_str.split()
                date_key = " ".join(date_parts[:3])  # Jour, Mois, Numéro de jour
                commit_frequency[date_key] = commit_frequency.get(date_key, 0) + 1
            except:
                pass

        # Analyse des fichiers modifiés récemment
        success, output = self._run_git_command(['diff', '--name-only', 'HEAD~5', 'HEAD'])
        recently_modified = output.split('\n') if success else []

        # Préparer le résultat
        analysis = {
            'repo_info': self.repo_info,
            'commit_stats': {
                'total_commits': len(commits),
                'authors': authors,
                'frequency': commit_frequency
            },
            'recently_modified': recently_modified,
            'insights': self._generate_insights(commits, authors, recently_modified)
        }

        return analysis

    def _generate_insights(self, commits, authors, recently_modified):
        """Génère des insights basés sur l'analyse du dépôt"""
        insights = []

        # Vérifier l'activité récente
        if len(commits) < 3:
            insights.append("Peu d'activité récente dans ce dépôt.")

        # Vérifier la diversité des contributeurs
        if len(authors) == 1:
            insights.append("Ce dépôt a un seul contributeur récent.")
        elif len(authors) > 3:
            insights.append(f"Ce dépôt a {len(authors)} contributeurs récents.")

        # Vérifier les fichiers modifiés fréquemment
        file_counts = {}
        for file in recently_modified:
            if file:
                file_counts[file] = file_counts.get(file, 0) + 1

        frequently_modified = [f for f, count in file_counts.items() if count > 1]
        if frequently_modified:
            insights.append(f"{len(frequently_modified)} fichiers ont été modifiés plusieurs fois récemment.")

        # Vérifier l'état actuel
        if self.repo_info['status']['modified']:
            insights.append(f"Il y a {len(self.repo_info['status']['modified'])} fichiers modifiés non commités.")

        if self.repo_info['status']['untracked']:
            insights.append(f"Il y a {len(self.repo_info['status']['untracked'])} fichiers non suivis.")

        # Si pas d'insights, ajouter un message par défaut
        if not insights:
            insights.append("Le dépôt semble être en bon état.")

        return insights

    def initialize_repo(self, path: str) -> bool:
        """Initialise un nouveau dépôt Git"""
        if not os.path.isdir(path):
            self.ui.print_error(f"Le chemin {path} n'est pas un répertoire valide")
            return False

        success, output = self._run_git_command(['init'], cwd=path)

        if success:
            self.repo_path = path
            self.is_git_repo = True
            self.current_branch = 'master'  # ou 'main' selon la configuration Git
            self.refresh_repo_info()
            self.ui.print_success(f"Dépôt Git initialisé dans {path}")
            return True
        else:
            self.ui.print_error(f"Erreur lors de l'initialisation du dépôt: {output}")
            return False

    async def generate_commit_message_with_claude(
            self, diff_text: str, client, model: str = None
    ) -> str:
        """Génère un message de commit intelligent en utilisant Claude"""
        if not diff_text:
            return "Mise à jour du code"

        # Construire le prompt pour Claude
        prompt = f"""
En tant qu'expert en développement logiciel, analyse ce diff Git et génère un message 
de commit clair, concis et informatif qui résume les changements.

Le message doit :
1. Commencer par un verbe à l'infinitif ou au présent (ex: "Ajoute", "Corrige", "Mise à jour")
2. Être concis (moins de 70 caractères pour la première ligne)
3. Décrire l'impact ou la motivation du changement, pas juste ce qui a été modifié
4. Mentionner les composants principaux affectés
5. Suivre les conventions de Conventional Commits (https://www.conventionalcommits.org/)
   - Format: <type>(<scope>): <description>
   - Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
   - Exemple: "feat(auth): ajoute la validation par email"

Voici le diff :

```
{diff_text}
```

Réponds uniquement avec le message de commit, sans explications supplémentaires.
"""

        try:
            # Envoyer la requête à Claude
            response = await client.send_message(
                model or "claude-3-haiku-20240307",
                [{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3  # Température basse pour des résultats plus déterministes
            )

            # Nettoyer la réponse
            message = response.strip()

            # Limiter à la première ligne si nécessaire
            if "\n" in message:
                first_line = message.split("\n")[0].strip()
                if first_line and len(first_line) > 10:  # Vérifier que la première ligne est significative
                    return first_line

            return message

        except Exception as e:
            self.ui.print_warning(f"Erreur lors de la génération du message avec Claude: {str(e)}")
            # Fallback sur le générateur simple
            return self.generate_commit_message(diff_text)

    async def generate_conventional_commit(self, diff_text: str, client, model: str = None) -> Dict[str, str]:
        """
        Génère une description de commit normalisée selon les conventions Conventional Commits

        Returns:
            Dict contenant:
                - type: le type de commit (feat, fix, etc.)
                - scope: le périmètre concerné (optionnel)
                - description: la description courte
                - body: le corps du message (optionnel)
                - breaking_change: mention de breaking change (optionnel)
                - formatted: le message complet formaté
        """
        if not diff_text:
            return {
                "type": "chore",
                "scope": None,
                "description": "Mise à jour du code",
                "body": None,
                "breaking_change": None,
                "formatted": "chore: Mise à jour du code"
            }

        # Construire le prompt pour Claude
        prompt = f"""
En tant qu'expert Git, analyse ce diff et génère un message de commit selon la norme Conventional Commits.

Structure requise:
<type>(<scope>): <description>

[corps optionnel]

[BREAKING CHANGE: <description des changements non-rétrocompatibles>]

Règles à suivre:
1. Types acceptés: feat, fix, docs, style, refactor, perf, test, build, ci, chore
2. Le scope est optionnel et indique le composant affecté (ex: auth, ui, api)
3. La description doit être concise (max 70 caractères), commencer par un verbe à l'infinitif
4. Le corps est optionnel et doit expliquer le "pourquoi" du changement
5. "BREAKING CHANGE" est requis seulement si des changements cassent la compatibilité

Réponds avec un JSON ayant cette structure:
{{
  "type": "feat|fix|docs|style|refactor|perf|test|build|ci|chore",
  "scope": "composant affecté (optionnel)",
  "description": "description concise du changement",
  "body": "explication détaillée (optionnel)",
  "breaking_change": "description de changements non-compatibles (optionnel)",
  "formatted": "message complet au format conventional commit"
}}

Voici le diff:
```
{diff_text}
```
"""

        try:
            # Envoyer la requête à Claude
            response = await client.send_message(
                model or "claude-3-haiku-20240307",
                [{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.2
            )

            # Extraire le JSON de la réponse
            import json
            json_text = re.search(r'({.*})', response, re.DOTALL)

            if json_text:
                commit_data = json.loads(json_text.group(1))

                # Vérifier les données et fournir des valeurs par défaut si nécessaire
                if "type" not in commit_data or not commit_data["type"]:
                    commit_data["type"] = "chore"

                if "description" not in commit_data or not commit_data["description"]:
                    commit_data["description"] = "Mise à jour du code"

                # Générer le message formaté s'il n'existe pas
                if "formatted" not in commit_data or not commit_data["formatted"]:
                    scope_part = f"({commit_data.get('scope')})" if commit_data.get('scope') else ""
                    commit_data["formatted"] = f"{commit_data['type']}{scope_part}: {commit_data['description']}"

                    if commit_data.get('body'):
                        commit_data["formatted"] += f"\n\n{commit_data['body']}"

                    if commit_data.get('breaking_change'):
                        commit_data["formatted"] += f"\n\nBREAKING CHANGE: {commit_data['breaking_change']}"

                return commit_data

            # Fallback si le JSON n'est pas valide
            return {
                "type": "chore",
                "scope": None,
                "description": "Mise à jour du code",
                "body": None,
                "breaking_change": None,
                "formatted": "chore: Mise à jour du code"
            }

        except Exception as e:
            self.ui.print_warning(f"Erreur lors de la génération du message conventionnel: {str(e)}")
            return {
                "type": "chore",
                "description": "Mise à jour du code",
                "formatted": "chore: Mise à jour du code"
            }

    async def suggest_branch_name_with_claude(
            self, task_description: str, client, model: str = None
    ) -> str:
        """Suggère un nom de branche intelligent en utilisant Claude"""
        # Construire le prompt pour Claude
        prompt = f"""
En tant qu'expert en développement logiciel, suggère un nom de branche Git approprié 
pour la tâche suivante :

"{task_description}"

Le nom de branche doit :
1. Suivre le format "type/description-courte" (ex: feature/auth-system, fix/login-bug)
2. Utiliser uniquement des lettres minuscules, chiffres et tirets (pas d'espaces)
3. Être court mais descriptif (moins de 50 caractères)
4. Commencer par un type approprié: feature, fix, refactor, docs, chore, test, etc.

Réponds uniquement avec le nom de branche suggéré, sans explications supplémentaires.
"""

        try:
            # Envoyer la requête à Claude
            response = await client.send_message(
                model or "claude-3-haiku-20240307",
                [{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.3  # Température basse pour des résultats plus déterministes
            )

            # Nettoyer la réponse
            branch_name = response.strip()

            # Vérifier que le nom de branche est valide
            if "/" in branch_name and len(branch_name) <= 50 and not " " in branch_name:
                return branch_name

            # Si format incorrect, le nettoyer
            branch_name = re.sub(r'[^a-z0-9/-]', '-', branch_name.lower())
            if not branch_name.startswith(("feature/", "fix/", "refactor/", "docs/", "chore/", "test/")):
                branch_name = "feature/" + branch_name

            return branch_name[:50]  # Limiter à 50 caractères

        except Exception as e:
            self.ui.print_warning(f"Erreur lors de la suggestion de nom de branche avec Claude: {str(e)}")
            # Fallback sur le générateur simple
            return self.suggest_branch_name(task_description)

    async def analyze_code_changes_with_claude(
            self, diff_text: str, client, model: str = None
    ) -> Dict[str, Any]:
        """Analyse les changements de code avec Claude pour obtenir des insights"""
        if not diff_text or len(diff_text) < 10:
            return {
                "summary": "Pas assez de changements pour une analyse",
                "impact": "Minimal",
                "recommendations": []
            }

        # Construire le prompt pour Claude
        prompt = f"""
En tant qu'expert en revue de code, analyse ce diff Git et fournis une évaluation 
structurée des changements. Ignore tous les commentaires et me fournis uniquement 
un JSON valide avec les champs suivants :

{{
  "summary": "Résumé concis des changements en une phrase",
  "impact": "Évaluation de l'impact (Minimal/Modéré/Significatif)",
  "type_changes": ["Catégories de changements: bugfix, feature, refactor, style, etc."],
  "affected_components": ["Liste des composants/modules principaux affectés"],
  "potential_issues": ["Liste des problèmes potentiels ou risques"],
  "recommendations": ["Recommandations pour améliorer le code"]
}}

Voici le diff :

```
{diff_text}
```
"""

        try:
            # Envoyer la requête à Claude
            response = await client.send_message(
                model or "claude-3-haiku-20240307",
                [{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.2
            )

            # Essayer de parser la réponse comme JSON
            try:
                # Extraire le JSON de la réponse (au cas où Claude ajoute du texte avant/après)
                json_text = re.search(r'{.*}', response, re.DOTALL)
                if json_text:
                    import json
                    analysis = json.loads(json_text.group(0))
                    return analysis
            except Exception as json_err:
                self.ui.print_warning(f"Erreur lors du parsing de la réponse JSON: {str(json_err)}")

            # Si le JSON parsing échoue, retourner un résultat de base
            return {
                "summary": response[:100] + "..." if len(response) > 100 else response,
                "impact": "Indéterminé",
                "recommendations": []
            }

        except Exception as e:
            self.ui.print_warning(f"Erreur lors de l'analyse des changements avec Claude: {str(e)}")
            return {
                "summary": "Erreur lors de l'analyse avec Claude",
                "impact": "Indéterminé",
                "recommendations": ["Utilisez l'analyse manuelle des changements"]
            }

    async def generate_conventional_commit_message_with_claude(self, diff_text: str, client, model: str = None) -> str:
        """Génère un message de commit au format Conventional Commits avec Claude"""
        if not diff_text:
            return "chore: Mise à jour du code"

        try:
            # Utiliser la méthode generate_conventional_commit pour obtenir la structure du message
            commit_data = await self.generate_conventional_commit(diff_text, client, model)

            # Retourner le message formaté
            return commit_data.get("formatted", "chore: Mise à jour du code")

        except Exception as e:
            self.ui.print_warning(f"Erreur lors de la génération du message conventionnel: {str(e)}")
            # Fallback sur le générateur simple
            return "chore: " + self.generate_commit_message(diff_text)

    def stash_changes(self, name: Optional[str] = None, apply_immediately: bool = False) -> bool:
        """Crée un stash des modifications courantes avec un nom personnalisé et option pour l'appliquer immédiatement"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        # Vérifier s'il y a des changements à stasher
        status = self._get_repo_status()
        if status['is_clean']:
            self.ui.print_warning("Aucun changement à stasher")
            return False

        # Commande pour créer le stash
        command = ['stash', 'push']
        if name:
            command.extend(['-m', name])

        success, output = self._run_git_command(command)

        if not success:
            self.ui.print_error(f"Erreur lors de la création du stash: {output}")
            return False

        self.ui.print_success(f"Stash créé avec succès: {output}")

        # Si demandé, appliquer immédiatement le stash
        if apply_immediately:
            success, apply_output = self._run_git_command(['stash', 'apply', 'stash@{0}'])
            if success:
                self.ui.print_success("Stash appliqué avec succès")
            else:
                self.ui.print_error(f"Erreur lors de l'application du stash: {apply_output}")
                return False

        self.refresh_repo_info()
        return True

    def merge_branch(self, source_branch: str, strategy: str = 'default',
                     no_commit: bool = False, squash: bool = False) -> bool:
        """Fusionne une branche dans la branche courante avec options avancées"""
        if not self.is_git_repo:
            self.ui.print_error("Vous n'êtes pas dans un dépôt Git valide")
            return False

        # Vérifier que la branche source existe
        branches = self._get_branches()
        if source_branch not in branches:
            self.ui.print_error(f"La branche {source_branch} n'existe pas")
            return False

        # Construire la commande de fusion
        command = ['merge']

        # Ajouter les options
        if strategy != 'default':
            if strategy in ['recursive', 'resolve', 'octopus', 'ours', 'subtree']:
                command.extend([f'--strategy={strategy}'])
            else:
                self.ui.print_warning(
                    f"Stratégie {strategy} non reconnue, utilisation de la stratégie par défaut"
                )

        if no_commit:
            command.append('--no-commit')

        if squash:
            command.append('--squash')

        # Ajouter la branche source
        command.append(source_branch)

        # Exécuter la commande
        success, output = self._run_git_command(command)

        if success:
            self.ui.print_success(
                f"Fusion de {source_branch} dans {self.current_branch} réussie"
            )
            self.refresh_repo_info()
            return True
        else:
            self.ui.print_error(f"Erreur lors de la fusion: {output}")
            # Vérifier s'il s'agit d'un conflit
            if "Automatic merge failed" in output or "CONFLICT" in output:
                self.ui.print_warning(
                    "Des conflits ont été détectés. Vous devez les résoudre manuellement."
                )
            return False

    def get_enhanced_log(
            self, format_type: str = 'default', count: int = 10,
            show_graph: bool = False, filter_author: Optional[str] = None
    ) -> str:
        """Affiche un historique Git amélioré avec différents formats et filtres"""
        if not self.is_git_repo:
            return "Vous n'êtes pas dans un dépôt Git valide"

        # Définir les formats disponibles
        formats = {
            'default': '--pretty=format:"%C(auto)%h %C(blue)%ad%C(auto)%d %C(reset)%s '
                       '%C(dim green)[%an]" --date=short',
            'detailed': '--pretty=format:"%C(auto)%h %C(blue)%ad%C(auto)%d %C(reset)%s '
                        '%C(dim green)[%an <%ae>]" --date=iso',
            'summary': '--pretty=format:"%C(auto)%h %C(reset)%s" --date=short',
            'stats': '--stat',
            'full': '--pretty=full',
        }

        # Sélectionner le format
        log_format = formats.get(format_type, formats['default'])

        # Construire la commande
        command = ['log', f'-{count}']

        # Ajouter le format
        for fmt in log_format.split():
            command.append(fmt)

        # Ajouter le graphe si demandé
        if show_graph:
            command.append('--graph')

        # Filtrer par auteur si spécifié
        if filter_author:
            command.append(f'--author={filter_author}')

        # Exécuter la commande
        success, output = self._run_git_command(command)

        if success:
            return output or "Aucun commit trouvé avec ces critères"
        else:
            return f"Erreur lors de la récupération du log: {output}"

    def visualize_git_history(self, max_count: int = 30, include_all_branches: bool = False,
                              compact: bool = False, include_stats: bool = False) -> str:
        """
        Génère une visualisation ASCII avancée de l'historique Git avec branches et relations

        Args:
            max_count: Nombre maximum de commits à afficher
            include_all_branches: Si True, inclut toutes les branches, même si non actives
            compact: Si True, utilise un format plus compact
            include_stats: Si True, inclut des statistiques pour chaque commit

        Returns:
            Représentation visuelle ASCII de l'historique Git
        """
        if not self.is_git_repo:
            return "Vous n'êtes pas dans un dépôt Git valide"

        # Construire la commande avec les bonnes options
        command = ['log']
        command.append(f'-{max_count}')
        command.append('--graph')  # Option clé pour le graphe ASCII

        if include_all_branches:
            command.append('--all')

        if include_stats:
            command.append('--stat')

        # Format personnalisé pour mieux visualiser les branches
        format_style = 'format:"%C(auto)%h %C(blue)%ad%C(auto)%d %C(reset)%s"'
        if not compact:
            format_style = 'format:"%C(auto)%h %C(blue)%ad%C(auto)%d %C(reset)%s %C(dim green)[%an]"'

        command.append(f'--pretty={format_style}')
        command.append('--date=short')

        # Ajouter des couleurs et utiliser Unicode pour améliorer la visualisation
        command.append('--color=always')

        # Exécuter la commande
        success, output = self._run_git_command(command)

        if not success:
            return f"Erreur lors de la génération de la visualisation: {output}"

        # Améliorer l'affichage avec des caractères Unicode pour remplacer les ASCII standards
        enhanced_output = output
        if not compact:
            # Remplacer les caractères ASCII par des caractères Unicode plus élégants
            replacements = {
                '|': '│',
                '/': '╱',
                '\\': '╲',
                '*': '●',
                '+': '┼',
            }
            for ascii_char, unicode_char in replacements.items():
                enhanced_output = enhanced_output.replace(ascii_char, unicode_char)

        return enhanced_output

    def assist_merge_conflicts(self, source_branch: str) -> Dict[str, Any]:
        """
        Analyse les conflits de fusion et fournit une assistance pour les résoudre

        Args:
            source_branch: Branche source qu'on tente de fusionner

        Returns:
            Dictionnaire contenant les informations sur les conflits et suggestions
        """
        if not self.is_git_repo:
            return {"error": "Vous n'êtes pas dans un dépôt Git valide"}

        # Vérifier si une fusion est en cours
        merge_head_path = os.path.join(self.repo_path, '.git', 'MERGE_HEAD')
        if not os.path.exists(merge_head_path):
            return {"error": "Aucune fusion en cours"}

        # Obtenir la liste des fichiers en conflit
        success, output = self._run_git_command(['diff', '--name-only', '--diff-filter=U'])

        if not success:
            return {"error": f"Erreur lors de la récupération des conflits: {output}"}

        conflict_files = [f for f in output.strip().split('\n') if f]

        # Analyser chaque fichier en conflit
        conflicts_analysis = []
        for file_path in conflict_files:
            # Lire le contenu du fichier avec les marqueurs de conflit
            try:
                with open(os.path.join(self.repo_path, file_path), 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                conflicts_analysis.append({
                    "file": file_path,
                    "error": f"Impossible de lire le fichier: {str(e)}"
                })
                continue

            # Trouver les sections en conflit
            conflicts_in_file = []
            conflict_markers = [
                ("<<<<<<< HEAD", "=======", ">>>>>>> " + source_branch)
            ]

            for start_marker, middle_marker, end_marker in conflict_markers:
                start_idx = 0
                while True:
                    # Chercher le début du conflit
                    start_idx = content.find(start_marker, start_idx)
                    if start_idx == -1:
                        break

                    # Chercher le milieu et la fin du conflit
                    middle_idx = content.find(middle_marker, start_idx)
                    if middle_idx == -1:
                        break

                    end_idx = content.find(end_marker, middle_idx)
                    if end_idx == -1:
                        break

                    # Extraire les versions en conflit
                    current_version = content[start_idx + len(start_marker):middle_idx].strip()
                    incoming_version = content[middle_idx + len(middle_marker):end_idx].strip()

                    # Analyser le conflit
                    conflict_type = self._determine_conflict_type(current_version, incoming_version)
                    suggested_resolution = self._suggest_conflict_resolution(
                        current_version, incoming_version, conflict_type
                    )

                    conflicts_in_file.append({
                        "type": conflict_type,
                        "current_version": current_version,
                        "incoming_version": incoming_version,
                        "suggestion": suggested_resolution
                    })

                    # Avancer au-delà de ce conflit
                    start_idx = end_idx + len(end_marker)

            conflicts_analysis.append({
                "file": file_path,
                "conflicts_count": len(conflicts_in_file),
                "conflicts": conflicts_in_file
            })

        return {
            "source_branch": source_branch,
            "target_branch": self.current_branch,
            "conflict_files_count": len(conflict_files),
            "conflict_files": conflict_files,
            "analysis": conflicts_analysis,
            "command_suggestions": [
                f"git checkout --ours -- <file>   # Pour garder la version de {self.current_branch}",
                f"git checkout --theirs -- <file> # Pour garder la version de {source_branch}",
                "git add <file>                  # Après résolution manuelle"
            ]
        }

    def _determine_conflict_type(self, current: str, incoming: str) -> str:
        """
        Détermine le type de conflit entre deux versions

        Args:
            current: Version actuelle
            incoming: Version entrante

        Returns:
            Type de conflit ('ajout', 'suppression', 'modification', 'complexe')
        """
        if not current and incoming:
            return "ajout"
        elif current and not incoming:
            return "suppression"
        elif current.strip() == incoming.strip():
            return "aucun_changement"

        # Analyse plus fine des modifications
        words_current = set(current.split())
        words_incoming = set(incoming.split())

        common_words = words_current.intersection(words_incoming)
        total_words = len(words_current.union(words_incoming))

        if total_words > 0 and len(common_words) / total_words > 0.7:
            return "modification_mineure"

        return "modification_majeure"

    def _suggest_conflict_resolution(self, current: str, incoming: str, conflict_type: str) -> str:
        """
        Suggère une résolution pour un conflit

        Args:
            current: Version actuelle
            incoming: Version entrante
            conflict_type: Type de conflit

        Returns:
            Suggestion de résolution
        """
        if conflict_type == "aucun_changement":
            return current  # Les deux versions sont identiques

        if conflict_type == "ajout":
            return incoming  # Garder l'ajout

        if conflict_type == "suppression":
            return ""  # Confirmer la suppression

        if conflict_type == "modification_mineure":
            # Pour les modifications mineures, on pourrait tenter une fusion manuelle
            # mais pour simplifier on suggère de garder la version entrante
            return incoming

        # Par défaut pour les modifications complexes, suggérer un examen manuel
        return "## Conflit complexe nécessitant une résolution manuelle ##"

    def generate_sprint_retrospective(self, days: int = 14,
                                      include_stats: bool = True,
                                      categorize: bool = True) -> Dict[str, Any]:
        """
        Génère une rétrospective de sprint basée sur l'activité Git récente

        Args:
            days: Nombre de jours à inclure dans la rétrospective
            include_stats: Si True, inclut des statistiques détaillées
            categorize: Si True, catégorise les commits par type

        Returns:
            Dictionnaire contenant les informations de rétrospective
        """
        if not self.is_git_repo:
            return {"error": "Vous n'êtes pas dans un dépôt Git valide"}

        # Obtenir la date de début (il y a 'days' jours)
        import datetime
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        start_date_str = start_date.strftime("%Y-%m-%d")

        # Récupérer les commits sur cette période
        command = [
            'log',
            f'--since={start_date_str}',
            '--pretty=format:%h|%an|%ad|%s|%d',
            '--date=short'
        ]

        success, output = self._run_git_command(command)

        if not success or not output:
            return {
                "error": f"Aucun commit trouvé depuis {start_date_str}"
                if not output else f"Erreur: {output}"
            }

        # Parser les commits
        commits = []
        for line in output.strip().split('\n'):
            parts = line.split('|')
            if len(parts) >= 4:
                commit = {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                    "refs": parts[4] if len(parts) > 4 else ""
                }
                commits.append(commit)

        # Statistiques de base
        authors_stats = {}
        for commit in commits:
            author = commit["author"]
            if author not in authors_stats:
                authors_stats[author] = {
                    "commit_count": 0,
                    "first_commit_date": None,
                    "last_commit_date": None
                }

            authors_stats[author]["commit_count"] += 1

            commit_date = commit["date"]
            if (not authors_stats[author]["first_commit_date"] or
                    commit_date < authors_stats[author]["first_commit_date"]):
                authors_stats[author]["first_commit_date"] = commit_date

            if (not authors_stats[author]["last_commit_date"] or
                    commit_date > authors_stats[author]["last_commit_date"]):
                authors_stats[author]["last_commit_date"] = commit_date

        # Catégoriser les commits si demandé
        commit_categories = {}
        if categorize:
            # Catégories communes basées sur les messages de commit
            categories = {
                "feature": ["feat", "feature", "add", "implement"],
                "fix": ["fix", "bug", "resolve", "correct"],
                "refactor": ["refactor", "clean", "improve"],
                "docs": ["doc", "comment", "readme"],
                "test": ["test", "spec", "coverage"],
                "chore": ["chore", "update", "upgrade"],
                "style": ["style", "format", "lint"],
                "perf": ["perf", "performance", "optimize"]
            }

            # Détecter la catégorie de chaque commit
            for commit in commits:
                message = commit["message"].lower()
                assigned_category = None

                # Chercher dans le format Conventional Commits d'abord
                conventional_match = re.match(r'^(\w+)(\([\w-]+\))?:', message)
                if conventional_match:
                    category_type = conventional_match.group(1)
                    for cat, keywords in categories.items():
                        if category_type in keywords:
                            assigned_category = cat
                            break

                # Si pas trouvé, chercher des mots-clés
                if not assigned_category:
                    for cat, keywords in categories.items():
                        if any(keyword in message for keyword in keywords):
                            assigned_category = cat
                            break

                # Catégorie par défaut
                if not assigned_category:
                    assigned_category = "other"

                if assigned_category not in commit_categories:
                    commit_categories[assigned_category] = []

                commit_categories[assigned_category].append(commit)

        # Composer la rétrospective
        retrospective = {
            "period": {
                "start_date": start_date_str,
                "end_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "days": days
            },
            "summary": {
                "total_commits": len(commits),
                "active_authors": len(authors_stats),
                "commits_per_day": round(len(commits) / max(1, days), 2)
            },
            "authors": authors_stats,
            "commits": commits[:10],  # Limiter à 10 pour éviter un rapport trop long
            "has_more_commits": len(commits) > 10
        }

        if categorize:
            retrospective["categories"] = {
                category: len(cat_commits)
                for category, cat_commits in commit_categories.items()
            }
            retrospective["categorized_commits"] = commit_categories

        if include_stats:
            # Récupérer des statistiques supplémentaires
            stats_command = [
                'diff',
                f'--stat=1000',
                f'@{{{days}}}',
                'HEAD'
            ]

            stats_success, stats_output = self._run_git_command(stats_command)
            if stats_success:
                # Récupérer le nombre de fichiers modifiés et les lignes ajoutées/supprimées
                stats_lines = stats_output.strip().split('\n')
                file_stats = []

                for line in stats_lines:
                    if '|' in line and ('+' in line or '-' in line):
                        parts = line.split('|')
                        if len(parts) >= 2:
                            file_name = parts[0].strip()
                            changes = parts[1].strip()

                            # Extraire les statistiques de modifications
                            additions = changes.count('+')
                            deletions = changes.count('-')

                            file_stats.append({
                                "file": file_name,
                                "additions": additions,
                                "deletions": deletions,
                                "changes": additions + deletions
                            })

                # Ajouter le récapitulatif final s'il existe
                summary_line = None
                for line in reversed(stats_lines):
                    if 'changed' in line and ('insertion' in line or 'deletion' in line):
                        summary_line = line.strip()
                        break

                retrospective["file_stats"] = {
                    "files_changed": len(file_stats),
                    "most_changed_files": sorted(
                        file_stats,
                        key=lambda x: x["changes"],
                        reverse=True
                    )[:5],  # Top 5 des fichiers les plus modifiés
                    "summary": summary_line
                }

        return retrospective