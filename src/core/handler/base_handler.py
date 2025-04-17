
class BaseHandler:

    def __init__(self, config, client, ui, api_key):
        self.client = client
        self.ui = ui
        self.api_key = api_key
        self.config = config


    async def process(self, args):
        pass