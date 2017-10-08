import asyncio

import aiohttp.web as web
import requests

from services.receiver_extensions import QueueDBWriter, StockGymEndPoint


class Receiver(web.Server):
    topic_url = 'http://127.0.0.1:1111'
    companies = list(sorted(eval(requests.get(topic_url, params={'q': 'topics'}).text).keys()))

    def __init__(self, **kwargs):
        super(Receiver, self).__init__(self.process_request, **kwargs)
        self.queues = [asyncio.Queue() for _ in range(4)]
        self.expected_keys = ['article', 'blog', 'reddit', 'twitter', 'stock']
        QueueDBWriter(self.queues[0], self.companies).start()
        StockGymEndPoint(self.queues[1]).start()
        # Thread(target=lambda: Controller(self.queues[2]).mainloop()).start()

    async def on_post(self, request):
        data = await request.read()
        json = eval(data)
        assert set(json.keys()) == set(self.expected_keys)
        print(json.copy().popitem()[1].copy().popitem())
        for queue in self.queues:
            await queue.put(json)
        return web.Response(text='Success!', status=200)

    async def on_get(self):
        item = await self.queues[-1].get()
        while not self.queues[-1].empty():
            item = await self.queues[-1].get()
        await self.queues[-1].put(item)
        for k in item:
            if 'time' in item[k].keys():
                _ = item[k].pop('time')
        return web.Response(body=str(item), status=200)

    async def process_request(self, request):
        try:
            if request.method == 'POST':
                return await self.on_post(request)

            elif request.method == 'GET':
                return await self.on_get()

        except (TypeError, AssertionError):
            return web.Response(text="Incorrectly formatted request", status=404)

    @staticmethod
    async def run(address):
        loop = asyncio.get_event_loop()
        server = Receiver()

        await loop.create_server(server, *address)
        while True:
            try:
                await asyncio.sleep(60)
            except KeyboardInterrupt:
                break
        await server.shutdown()
        loop.close()


if __name__ == '__main__':
    add = '127.0.0.1', 9999
    #add = '192.168.1.53', 9999
    main_loop = asyncio.get_event_loop()
    main_loop.run_until_complete(Receiver.run(add))
