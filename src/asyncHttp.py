import aiohttp

class AsyncHTTP:
    session: aiohttp.ClientSession | None = None

    @classmethod
    async def init(cls):
        if cls.session is None:
            timeout = aiohttp.ClientTimeout(total=20)
            cls.session = aiohttp.ClientSession(timeout=timeout)

    @classmethod
    async def get(cls, url: str):
        if cls.session is None:
            await cls.init()
        async with cls.session.get(url) as resp: # type: ignore
            resp.raise_for_status()
            return await resp.read()

    @classmethod
    async def close(cls):
        if cls.session:
            await cls.session.close()
