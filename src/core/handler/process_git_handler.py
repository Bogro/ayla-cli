import os

from src.core.handler.base_handler import BaseHandler
from src.core.modules.git_manager import GitManager


class ProcessGitHandler(BaseHandler):

    def __init__(self, config, client, ui, api_key, git_manager):
        super().__init__(config, client, ui, api_key)
        self.git_manager = git_manager

    async def process(self, args):

        # Initialiser le gestionnaire Git si ce n'est pas déjà fait
        if not hasattr(self, 'git_manager'):
            self.git_manager = GitManager(self.ui)
            # Utiliser le répertoire courant comme dépôt
            if not self.git_manager.set_repo_path(os.getcwd()):
                self.ui.print_error("Le répertoire courant n'est pas un dépôt Git valide")
                return True

        # Définir le client pour les appels à l'IA
        self.git_manager.set_client(self.client)

        try:
            # Traiter chaque commande Git
            if args.git_commit:
                # Obtenir le diff actuel
                diff = self.git_manager.get_detailed_diff()
                # Générer un message de commit avec Claude
                message = await self.git_manager.generate_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                # Créer le commit
                self.git_manager.commit_changes(message)

            elif args.git_branch and args.git_branch != True:
                # Suggérer un nom de branche et la créer
                branch_name = await self.git_manager.suggest_branch_name(args.description)
                self.git_manager.switch_branch(branch_name, create=True)

            elif args.git_analyze:
                # Analyser le dépôt
                analysis = await self.git_manager.analyze_repository(api_key)
                self.git_manager.display_git_analysis(analysis)

            elif args.git_diff_analyze:
                # Analyser les changements
                analysis = self.git_manager.analyze_changes()
                self.git_manager.display_git_analysis(analysis, 'diff')

            elif args.git_conventional_commit:
                # Générer un message de commit conventionnel
                diff = self.git_manager.get_detailed_diff()
                message = await self.git_manager.generate_conventional_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                self.git_manager.commit_changes(message)

            elif args.git_create_branch and args.git_create_branch != True:
                # Créer une nouvelle branche
                self.git_manager.switch_branch(args.git_create_branch, create=True)

            elif args.git_commit_and_push:
                # Commit et push en une seule commande
                diff = self.git_manager.get_detailed_diff()
                message = await self.git_manager.generate_commit_message_with_claude(
                    diff, self.client, self.config.DEFAULT_MODEL
                )
                if self.git_manager.commit_changes(message):
                    self.git_manager.push_changes()

            elif args.git_stash:
                # Gérer les stash
                self.git_manager.stash_changes(
                    name=args.git_stash if isinstance(args.git_stash, str) else None
                )

            elif args.git_stash_apply:
                # Appliquer le dernier stash
                success, output = self.git_manager._run_git_command(['stash', 'apply'])
                if success:
                    self.ui.print_success("Stash appliqué avec succès")
                else:
                    self.ui.print_error(f"Erreur lors de l'application du stash: {output}")

            elif args.git_merge:
                # Fusionner une branche
                self.git_manager.merge_branch(args.git_merge)

            elif args.git_merge_squash:
                # Fusionner une branche en squash
                self.git_manager.merge_branch(args.git_merge_squash, squash=True)

            elif args.git_log:
                # Afficher le log amélioré
                format_type = getattr(args, 'git_log_format', 'default')
                count = getattr(args, 'git_log_count', 10)
                show_graph = getattr(args, 'git_log_graph', False)
                log = self.git_manager.get_enhanced_log(
                    format_type=format_type,
                    count=count,
                    show_graph=show_graph
                )
                self.ui.print_info(log)

            elif args.git_visualize:
                # Visualiser l'historique
                viz = self.git_manager.visualize_git_history(
                    include_all_branches=True,
                    include_stats=True
                )
                self.ui.print_info(viz)

            elif args.git_conflict_assist:
                # Assister dans la résolution des conflits
                try:
                    conflicts = self.git_manager.assist_merge_conflicts(
                        self.git_manager.current_branch
                    )
                    self.ui.print_info(conflicts)
                except Exception as e:
                    self.ui.print_info(str(e))

            elif args.git_retrospective:
                try:
                    # Générer une rétrospective
                    days = args.git_retrospective if isinstance(args.git_retrospective, int) else 14
                    retro = self.git_manager.generate_sprint_retrospective(days=days)
                    self.git_manager.display_git_analysis(retro, 'retro')
                except Exception as e:
                    self.ui.print_info(str(e))

            return True

        except Exception as e:
            self.ui.print_error(f"Erreur lors du traitement de la commande Git: {str(e)}")
            return True
