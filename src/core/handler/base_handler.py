
class BaseHandler:

    def __init__(self, client, ui, crew_manager, api_key):
        self.client = client
        self.ui = ui
        self.api_key = api_key
        self.crew_manager = crew_manager


    async def process(self, args):
        pass