import asyncio
import os
import re

import aiohttp.web as web


class FileKeeper:
    """Object for easily retrieving api keys and topic dictionaries"""
    def __init__(self):
        self.base = 'data/'
        self.data = {}
        self.schemas = {}
        self.load_files()
        self.set_schemas()

    def load_files(self):
        """Loads required api and topic dictionary files into memory"""
        files = os.listdir(self.base)
        for fn in files:
            with open(os.path.join(self.base, fn)) as f:
                lines = f.read().splitlines()
            # if topic dictionary request
            if any(sub in fn for sub in ['topics', 'subreddits']):
                data = {}
                for ln in lines:
                    topic, queries = ln.split(':')
                    data[topic] = queries.split(',')
            # else api request
            else:
                data = [ln.split('|') for ln in lines]
                # if single api key return only string of key, else return list
                if len(data) == 1:
                    data = '"{}"'.format(data[0][0])
            self.data[fn.replace('.txt', '')] = data

    def set_schemas(self):
        """Sets schemas for accepting new api keys"""
        for i in self.data:
            self.schemas[i] = self.schema([8, 4, 4, 4, 12])

    @staticmethod
    def schema(l):
        """Character pattern for api key to ensure validity"""
        s = '[0-9a-zA-Z]{%s}-' * len(l)
        r = s % tuple(i for i in l)
        return r[:-1]

    def __getitem__(self, item):
        return self.data[item]

    def update(self, key, source):
        """Updates api keys with provided key from source"""
        t = 'w' if source == 'twingly' else 'a'
        search = re.compile(self.schemas[source])
        if len(re.findall(search, key)) != 1:
            raise KeyError
        else:
            with open(os.path.join(self.base, source + '.txt'), t) as f:
                f.write(key + '\n')


class APIServer(web.Server):
    """Asynchronous api server for requesting api keys and topic dictionaries"""
    def __init__(self):
        super(APIServer, self).__init__(self.process_request)
        self.files = FileKeeper()

    def on_data(self, params):
        source = params.get('q', None)
        if source is None:
            raise TypeError
        else:
            return str(self.files[source])

    def on_post(self, params, data):
        try:
            t = params['q']
            auth = data['auth']
            self.files.update(auth, t)
            return 'Success', 200
        except KeyError:
            return 'Failed!', 401

    async def process_request(self, request):
        params = request.query or {}
        try:
            if request.method == 'GET':
                result = self.on_data(params)
                return web.Response(text=result, status=200)
            elif request.method == 'POST':
                data = await request.post()
                result, code = self.on_post(params, data)
                return web.Response(text=result, status=code)
        except (KeyError, TypeError):
            return web.Response(text='Incorrect request', status=404)

    @staticmethod
    async def run(api_address):
        """Main server running function - creates and runs proxy server asynchronously"""
        server = APIServer()
        loop = asyncio.get_event_loop()
        await loop.create_server(server, *api_address)

        while True:
            try:
                await asyncio.sleep(60)
            except KeyboardInterrupt:
                break

        await server.shutdown()
        loop.close()


if __name__ == '__main__':
    aa = '127.0.0.1', 1111
    # aa = '192.168.0.100', 1111
    main_loop = asyncio.get_event_loop()
    main_loop.run_until_complete(APIServer.run(aa))
