#!/usr/bin/env python3
"""
Ayla CLI - Une interface en ligne de commande avancé
"""
import asyncio
import sys

from src.cli import AylaCli

try:
    from anthropic import Anthropic, RateLimitError, APIStatusError, APIConnectionError, APIError
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.theme import Theme
    from rich import box
    import nest_asyncio
except ImportError:
    print("Installation des dépendances requises...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "anthropic", "rich", "nest_asyncio"])
    from anthropic import Anthropic, RateLimitError, APIStatusError, APIConnectionError, APIError
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.theme import Theme
    from rich import box
    import nest_asyncio


async def main():
    """Point d'entrée de l'application"""
    app = AylaCli()
    await app.run()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())