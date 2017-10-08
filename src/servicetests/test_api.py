import unittest

import aiohttp

from servicetests import synchronous


class TestAPI(unittest.TestCase):
    server = 'http://127.0.0.1:1111'
    #server = 'http://192.168.0.100:1111'

    @synchronous
    async def test_api_request_no_params(self):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.server) as resp:
                assert resp.status == 404, 'No params request for api key failed'

    @synchronous
    async def test_api_request_correct_params(self):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.server, params={'q': 'topics'}) as resp:
                assert resp.status == 200, 'Correct request for api key failed'
                text = await resp.text()
                assert eval(text), 'No authentication in return data'

    @synchronous
    async def test_api_request_incorrect_params(self):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.server, params={'a': 1}) as resp:
                assert resp.status == 404, 'Incorrect request for api key failed'
