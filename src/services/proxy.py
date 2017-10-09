import asyncio
import heapq
import random

import aiohttp
import aiohttp.web as web


class ProxyList:
    """Proxy heap that is sorted based on proxy speed"""
    def __init__(self):
        self.proxies = []
        self.used_proxies = set()
        self.n_fast_proxies = 0
        # Maps simple queries to longer actual query strings required for http request to proxy server
        self.query_map = {'speed': 'downloadSpeed',
                          'https': 'allowsHttps',
                          'post': 'allowsPost',
                          'user_agent': 'allowsUserAgentHeader'}

    @staticmethod
    def full_address(proxy_dict):
        """Returns address string of provided proxy that is ready for use with aiohttp"""
        return 'http://{}:{}'.format(proxy_dict['ip'], proxy_dict['port'])

    def add(self, proxy_dict):
        """Adds a proxy onto the heap"""
        try:
            if proxy_dict['ip'] not in self.used_proxies:
                self.used_proxies.add(proxy_dict['ip'])
                speed = float(proxy_dict['downloadSpeed'])
                proxy_dict['downloadSpeed'] = speed
                if speed >= 100:
                    self.n_fast_proxies += 1
                heapq.heappush(self.proxies, (1 / speed + random.random() / 100000, proxy_dict))
        except (KeyError, TypeError):
            print('Error occurred, here are the keys of the error causing proxy: ', proxy_dict.keys())

    def _pop(self, ind=0):
        """Internal pop, only removes proxy from heap if the heap is longer than 1"""
        if len(self.proxies) > 1:
            p = self.proxies.pop(ind)[1]
            if p['downloadSpeed'] > 100:
                self.n_fast_proxies -= 1
            return p
        else:
            return self.proxies[0][1]

    def pop(self, **proxy_kwargs):
        """Pops next fastest proxy with provided kwargs off of heap"""
        kwargs = {(i if i not in self.query_map.keys() else self.query_map[i]): v for i, v in proxy_kwargs.items()}
        speed = float(kwargs.pop('downloadSpeed', 0.))
        for ind, (_, proxy) in enumerate(self.proxies):
            if proxy['downloadSpeed'] >= speed:
                for k in kwargs:
                    try:
                        if not proxy[k]:
                            break
                    except KeyError:
                        continue
                else:
                    return self.full_address(self._pop(ind))

        else:
            return self.full_address(self._pop())


class ProxyServer(web.Server):
    """Proxy server - returns a random proxy on GET request filtered by provided params"""
    def __init__(self, api_addr):
        super(ProxyServer, self).__init__(self.process_request)
        self.proxy_list = ProxyList()
        self.api_server_url = 'http://{}:{}'.format(*api_addr)

    async def process_request(self, request):
        """Method to execute when a request is received by the server"""
        try:
            if request.method != 'GET':
                raise TypeError
            params = request.query or {}
            result = self.proxy_list.pop(**params)
            return web.Response(text=result, status=200)
        except TypeError:
            return web.Response(text="Incorrectly formatted request", status=404)

    def need_proxies(self, proxies_required):
        """Returns true if the proxy list has less than a certain amount of proxies"""
        return len(self.proxy_list.proxies) < proxies_required or self.proxy_list.n_fast_proxies < int(
            proxies_required / 5)

    @staticmethod
    async def get(sess, key):
        """Simple request method to return proxy json from `getproxylist` API"""
        params = {'apiKey': key, 'protocol': 'http', 'anonymity': 'high anonymity'}
        try:
            async with sess.get('https://api.getproxylist.com/proxy', params=params) as resp:
                return await resp.json()
        except Exception as e:
            _ = e  # we don't really care, this should succeed 99.99% of the time
            return None

    async def get_auth(self, session):
        """Gets API key from api server"""
        async with session.get(self.api_server_url, params={'q': 'proxy'}) as raw:
            resp = await raw.text()
        return eval(resp)

    async def gather_proxies(self, session, api_key, concurrent_requests=10):
        """Concurrently gathers certain amount of proxies, and adds all correct responses into the proxy list"""
        results = await asyncio.gather(*[self.get(session, api_key) for _ in range(concurrent_requests)])
        for result in results:
            if isinstance(result, dict):
                self.proxy_list.add(result)

    async def fetch_proxies(self, proxies_required=1000, concurrent_requests=10):
        """Daemon loop to constantly keep the proxy list full of good usable proxies"""
        async with aiohttp.ClientSession() as session:
            api_key = await self.get_auth(session)
            while True:
                if self.need_proxies(proxies_required):
                    await self.gather_proxies(session, api_key, concurrent_requests)
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(5)
                await asyncio.sleep(0)

    @staticmethod
    async def run(proxy_address, api_address, proxies_required=1000, concurrent_requests=10):
        """Main server running function - creates and runs proxy server asynchronously"""
        server = ProxyServer(api_address)
        loop = asyncio.get_event_loop()
        await loop.create_server(server, *proxy_address)
        await server.fetch_proxies(proxies_required, concurrent_requests)
        await server.shutdown()
        loop.close()


if __name__ == '__main__':
    # pa = '127.0.0.1', 9999
    # aa = '127.0.0.1', 1111
    pa = '192.168.0.100', 9999
    aa = '192.168.0.100', 1111
    p_required, c_requests = 1000, 10
    main_loop = asyncio.get_event_loop()
    main_loop.run_until_complete(ProxyServer.run(pa, aa, p_required, c_requests))
