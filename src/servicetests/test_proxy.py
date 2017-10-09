
import random
import unittest
import unittest.mock as mock

from services.proxy import ProxyList, ProxyServer
from servicetests import synchronous


def generate_random_proxy():
    """Returns randomly generated proxy with valid characteristics"""
    proxy = {
        "ip": "{}.{}.{}.{}".format(*[random.randint(5, 240) for _ in range(4)]),
        "port": random.randint(1000, 50000),
        "allowsUserAgentHeader": bool(random.randint(0, 1)),
        "allowsPost": bool(random.randint(0, 1)),
        "allowsHttps": bool(random.randint(0, 1)),
        "downloadSpeed": str(random.random() * 500)}
    return proxy


class TestProxyList(unittest.TestCase):
    """Test case for testing functionality of ProxyList proxy heap"""
    def setUp(self):
        self.list = ProxyList()

    def test_full_address(self):
        """Tests whether full address returns a correct proxy"""
        for _ in range(100):
            proxy = generate_random_proxy()
            addr = self.list.full_address(proxy)
            assert addr.startswith('http'), 'Did not return http proxy, {}'.format(addr)
            assert addr.endswith('{}:{}'.format(proxy['ip'], proxy['port'])), \
                'Proxy address not correctly formatted, {}'.format(addr)

    def test_add_slow_and_fast_proxies(self):
        """Tests whether slow and fast proxies are correctly added to the proxy list"""
        slow_proxy, fast_proxy = generate_random_proxy(), generate_random_proxy()
        slow_proxy['downloadSpeed'] = '5'
        fast_proxy['downloadSpeed'] = '200'
        self.list.add(slow_proxy)
        assert self.list.n_fast_proxies == 0, 'Fast proxies incremented but a slow proxy was added!'
        assert len(self.list.proxies) == 1, 'Proxy did not get added to proxy list'
        self.list.add(fast_proxy)
        assert self.list.n_fast_proxies == 1, 'Fast proxies not incremented but a fast proxy was added!'
        assert len(self.list.proxies) == 2, 'Proxy did not get added to proxy list'
        correct_form = [(1./200, fast_proxy), (1./5, slow_proxy)]
        approximate_proxies = [(round(i, 3), j) for i, j in self.list.proxies]
        assert approximate_proxies == correct_form, \
            'Proxies were not arranged correctly according to speed\n{}\n{}'.format(approximate_proxies, correct_form)

    def test_add_already_seen_proxy(self):
        """Tests whether list will correctly filter out already seen proxy"""
        proxy1, proxy2 = generate_random_proxy(), generate_random_proxy()
        proxy2['ip'] = proxy1['ip']
        self.list.add(proxy1)
        self.list.add(proxy2)
        assert len(self.list.proxies) == 1, 'Proxy that has already been seen was added to list!'

    def test_add_lots_of_proxies(self):
        """Tests whether adding a whole bunch of proxies will confuse the heap push"""
        count = 0
        for _ in range(10000):
            used_len = len(self.list.used_proxies)
            p = generate_random_proxy()
            self.list.add(p)
            count += len(self.list.used_proxies) - used_len
            assert len(self.list.proxies) == count, \
                'Proxy was not correctly pushed onto heap, incorrect list length, {}, {}'.format(len(self.list.proxies),
                                                                                                 count)

    def test_pop_proxy_no_kwargs(self):
        """Tests whether popping a proxy off the heap will always correctly return last available good proxy"""
        for _ in range(100):
            self.list.add(generate_random_proxy())
        # popping returns correct proxy
        for _ in range(99):
            p = self.list.pop()
            assert p.startswith('http'), 'Incorrect proxy returned'
        # popping last proxy and further with no proxies left returns last proxy
        p = self.list.pop()
        for _ in range(100):
            assert self.list.pop() == p, 'Last proxy not correctly returned'
            
    def test_pop_proxy_kwargs(self):
        """Tests whether popping a proxy with keyword arguments returns correct proxy"""
        t = [generate_random_proxy() for _ in range(4)]
        for i in range(4):
            t[i]["allowsUserAgentHeader"] = False
            t[i]["allowsPost"] = False
            t[i]["allowsHttps"] = False
            t[i]['downloadSpeed'] = str(5.0)
        agent, post, https, speed = t
        agent["allowsUserAgentHeader"] = True
        post["allowsPost"] = True
        https["allowsHttps"] = True
        speed['downloadSpeed'] = str(150)
        download = generate_random_proxy()
        download['downloadSpeed'] = str(1000)
        for p in agent, post, https, speed, download:
            self.list.add(p)
        
        fast_proxy = self.list.pop(speed=100)
        assert fast_proxy.split('://')[1] == '{}:{}'.format(download['ip'], download['port']), \
            'Did not return fastest proxy available'

        agent_proxy = self.list.pop(user_agent=True)
        assert agent_proxy.split('://')[1] == '{}:{}'.format(agent['ip'], agent['port']), \
            'Did not return user agent proxy'

        post_proxy = self.list.pop(post=True)
        assert post_proxy.split('://')[1] == '{}:{}'.format(post['ip'], post['port']), \
            'Did not return post proxy'

        https_proxy = self.list.pop(https=True)
        assert https_proxy.split('://')[1] == '{}:{}'.format(https['ip'], https['port']), \
            'Did not return https proxy'

        p = generate_random_proxy()
        p['allowsHttps'] = True
        p['allowsPost'] = True
        p['allowsUserAgentHeader'] = True
        p['downloadSpeed'] = str(1000)
        self.list.add(p)
        best_ever_proxy = self.list.pop(https=True, post=True, user_agent=True, speed=500)
        assert best_ever_proxy.split('://')[1] == '{}:{}'.format(p['ip'], p['port']), \
            'Did not return best proxy ever :('


class TestProxyServer(unittest.TestCase):
    """Test case for testing request handling of ProxyServer server"""
    proxy_address = '127.0.0.1', 9999
    api_address = '127.0.0.1', 1111

    @synchronous
    async def setUp(self):
        self.server = ProxyServer(self.api_address)
        for _ in range(500):
            self.server.proxy_list.add(generate_random_proxy())

    @synchronous
    async def test_process_correct_requests(self):
        """Test processing of correct proxy requests with varying kwargs"""
        request = mock.MagicMock()
        request.method = 'GET'
        queries = [None, {'https': True}, {'speed': 100}, {'https': True, 'post': True, 'speed': 100}]
        for q in queries:
            request.query = q
            res = await self.server.process_request(request)
            assert res.status == 200, 'Did not successfully return proxy, status - {}'.format(res.status)
            assert res.text.startswith('http'), 'Incorrect proxy returned by server!'

    @synchronous
    async def test_process_incorrect_request(self):
        """Test processing of incorrect proxy requests with varying kwargs"""
        request = mock.MagicMock()
        request.method = 'POST'
        res = await self.server.process_request(request)
        assert res.status == 404, 'Did not successfully fail to return proxy, status - {}'.format(res.status)
        request.method = 'GET'
        request.query = {'a': 1, 'b': []}
        res = await self.server.process_request(request)
        assert res.status == 200, 'Did not successfully return proxy, status - {}'.format(res.status)
