from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic


class CrewManager:
    def __init__(self, model = "claude-3-opus-20240229"):
        self.llm = None
        self.model = model

    def init_llm(self, anthropic_api_key: str):
        self.llm = ChatAnthropic(model=self.model, anthropic_api_key=anthropic_api_key)

    def create_research_crew(self, topic: str):
        """Crée une équipe d'agents pour la recherche sur un sujet."""

        # Création des agents spécialisés
        researcher = Agent(
            role='Chercheur',
            goal='Effectuer des recherches approfondies sur le sujet donné',
            backstory='Expert en recherche avec une grande capacité d\'analyse',
            allow_delegation=True,
            llm=self.llm
        )

        analyst = Agent(
            role='Analyste',
            goal='Analyser et synthétiser les informations de recherche',
            backstory='Spécialiste en analyse de données et synthèse',
            allow_delegation=True,
            llm=self.llm
        )

        writer = Agent(
            role='Rédacteur',
            goal='Rédiger un rapport clair et structuré',
            backstory='Écrivain expérimenté spécialisé dans la vulgarisation',
            allow_delegation=True,
            llm=self.llm
        )

        # Définition des tâches avec expected_output
        research_task = Task(
            description=f"Rechercher des informations détaillées sur : {topic}",
            expected_output="Un document contenant des informations détaillées et structurées sur le sujet, incluant des sources fiables.",
            agent=researcher
        )

        analysis_task = Task(
            description="Analyser les résultats de la recherche et identifier les points clés",
            expected_output="Une analyse synthétique des informations principales, avec des insights clés et des relations entre les différents concepts.",
            agent=analyst
        )

        writing_task = Task(
            description="Rédiger un rapport complet et structuré",
            expected_output="Un rapport bien structuré, clair et compréhensible présentant le sujet de manière cohérente avec une introduction, un développement et une conclusion.",
            agent=writer
        )

        # Création de l'équipe
        crew = Crew(
            agents=[researcher, analyst, writer],
            tasks=[research_task, analysis_task, writing_task],
            process=Process.sequential
        )

        return crew

    def create_code_review_crew(self, code: str):
        """Crée une équipe d'agents pour la revue de code."""

        security_expert = Agent(
            role='Expert en Sécurité',
            goal='Identifier les vulnérabilités et problèmes de sécurité',
            backstory='Expert en cybersécurité avec expérience en audit de code',
            allow_delegation=True,
            llm=self.llm
        )

        code_reviewer = Agent(
            role='Reviewer de Code',
            goal='Évaluer la qualité et la maintenabilité du code',
            backstory='Développeur senior avec expertise en bonnes pratiques',
            allow_delegation=True,
            llm=self.llm
        )

        optimizer = Agent(
            role='Optimiseur',
            goal='Proposer des améliorations de performance',
            backstory='Spécialiste en optimisation et performance',
            allow_delegation=True,
            llm=self.llm
        )

        # Tâches
        security_review = Task(
            description=f"Analyser le code pour les problèmes de sécurité:\n{code}",
            expected_output="Un rapport détaillé des vulnérabilités de sécurité trouvées dans le code, avec des recommandations pour les corriger.",
            agent=security_expert
        )

        code_quality_review = Task(
            description=f"Évaluer la qualité et la lisibilité du code:\n{code}",
            expected_output="Une évaluation complète de la qualité du code, incluant des recommandations pour améliorer sa structure, sa lisibilité et sa maintenabilité.",
            agent=code_reviewer
        )

        optimization_review = Task(
            description=f"Identifier les opportunités d'optimisation:\n{code}",
            expected_output="Une liste des optimisations possibles pour améliorer les performances du code, avec des exemples concrets de modifications à apporter.",
            agent=optimizer
        )

        # Création de l'équipe
        crew = Crew(
            agents=[security_expert, code_reviewer, optimizer],
            tasks=[security_review, code_quality_review, optimization_review],
            process=Process.sequential
        )

        return crew

    def create_code_analysis_crew(self, code: str, analysis_type: str = "general"):
        """Crée une équipe d'agents pour l'analyse de code."""

        security_expert = Agent(
            role='Expert en Sécurité',
            goal='Identifier les vulnérabilités et problèmes de sécurité',
            backstory='Expert en cybersécurité avec expérience en audit de code',
            allow_delegation=True,
            llm=self.llm
        )

        code_architect = Agent(
            role='Architecte Logiciel',
            goal='Analyser la structure et l\'architecture du code',
            backstory='Architecte senior avec expertise en patterns de conception',
            allow_delegation=True,
            llm=self.llm
        )

        performance_analyst = Agent(
            role='Analyste Performance',
            goal='Identifier les problèmes de performance et optimisations possibles',
            backstory='Spécialiste en optimisation et performance',
            allow_delegation=True,
            llm=self.llm
        )

        maintainability_expert = Agent(
            role='Expert Maintenabilité',
            goal='Évaluer la qualité et la maintenabilité du code',
            backstory='Expert en clean code et bonnes pratiques',
            allow_delegation=True,
            llm=self.llm
        )

        # Tâches
        tasks = []

        if analysis_type in ["general", "security"]:
            security_review = Task(
                description=f"Analyser le code pour les problèmes de sécurité:\n{code}",
                expected_output="Un rapport détaillé des vulnérabilités et risques de sécurité identifiés dans le code.",
                agent=security_expert
            )
            tasks.append(security_review)

        if analysis_type in ["general", "architecture"]:
            architecture_review = Task(
                description=f"Analyser l'architecture et la structure du code:\n{code}",
                expected_output="Une évaluation de l'architecture du code avec des diagrammes conceptuels et suggestions d'amélioration.",
                agent=code_architect
            )
            tasks.append(architecture_review)

        if analysis_type in ["general", "performance"]:
            performance_review = Task(
                description=f"Identifier les problèmes de performance:\n{code}",
                expected_output="Une analyse des goulots d'étranglement et des suggestions d'optimisation avec benchmark si possible.",
                agent=performance_analyst
            )
            tasks.append(performance_review)

        if analysis_type in ["general", "maintainability"]:
            maintainability_review = Task(
                description=f"Évaluer la maintenabilité du code:\n{code}",
                expected_output="Une évaluation de la maintenabilité avec des métriques de qualité et des suggestions d'amélioration.",
                agent=maintainability_expert
            )
            tasks.append(maintainability_review)

        # Création de l'équipe
        crew = Crew(
            agents=[security_expert, code_architect, performance_analyst, maintainability_expert],
            tasks=tasks,
            process=Process.sequential
        )

        return crew

    def create_project_analysis_crew(self, project_info: dict):
        """Crée une équipe d'agents pour l'analyse d'un projet."""

        architect = Agent(
            role='Architecte Système',
            goal='Analyser l\'architecture globale du projet',
            backstory='Architecte système expérimenté en conception de grands systèmes',
            allow_delegation=True,
            llm=self.llm
        )

        dependency_analyst = Agent(
            role='Analyste de Dépendances',
            goal='Analyser les dépendances et leur impact',
            backstory='Expert en gestion de dépendances et intégration',
            allow_delegation=True,
            llm=self.llm
        )

        tech_lead = Agent(
            role='Tech Lead',
            goal='Évaluer la cohérence technique et les choix technologiques',
            backstory='Leader technique expérimenté en gestion de projets',
            allow_delegation=True,
            llm=self.llm
        )

        documentation_expert = Agent(
            role='Expert Documentation',
            goal='Analyser et améliorer la documentation',
            backstory='Spécialiste en documentation technique et API',
            allow_delegation=True,
            llm=self.llm
        )

        # Tâches
        architecture_analysis = Task(
            description=f"Analyser l'architecture globale du projet:\n{project_info['structure']}",
            expected_output="Une analyse détaillée de l'architecture système avec identification des forces et faiblesses.",
            agent=architect
        )

        dependency_analysis = Task(
            description=f"Analyser les dépendances du projet:\n{project_info['dependencies']}",
            expected_output="Un rapport sur les dépendances, leur actualité, leur sécurité et leur compatibilité.",
            agent=dependency_analyst
        )

        tech_review = Task(
            description=f"Évaluer les choix technologiques:\n{project_info['tech_stack']}",
            expected_output="Une évaluation des choix technologiques en termes de pertinence, pérennité et adéquation au projet.",
            agent=tech_lead
        )

        documentation_review = Task(
            description=f"Analyser la documentation du projet:\n{project_info['documentation']}",
            expected_output="Une analyse de la qualité et de la complétude de la documentation avec suggestions d'amélioration.",
            agent=documentation_expert
        )

        # Création de l'équipe
        crew = Crew(
            agents=[architect, dependency_analyst, tech_lead, documentation_expert],
            tasks=[architecture_analysis, dependency_analysis, tech_review, documentation_review],
            process=Process.sequential
        )

        return crew