from __future__ import annotations

import asyncio
import requests
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
import json
from crawlee.browsers import PlaywrightBrowserPlugin, BrowserPool
from crawlee.browsers._playwright_browser_controller import PlaywrightBrowserController
from typing_extensions import override


from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

from playwright.async_api import BrowserContext, Page, ProxySettings
from typing_extensions import override

from crawlee.browsers._base_browser_controller import BaseBrowserController
from crawlee.browsers._types import BrowserType
from crawlee.fingerprint_suite import HeaderGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from playwright.async_api import Browser

    from crawlee.proxy_configuration import ProxyInfo
def modify_url_params(url: str, param_modifications: dict) -> str:
    """
    解析 URL 中的参数，对指定参数进行修改，然后重新拼装成新的 URL。

    :param url: 原始 URL
    :param param_modifications: 需要修改的参数及其新值，格式为 {param_name: new_value}
    :return: 修改后的 URL
    """
    # 解析 URL
    parsed_url = urlparse(url)
    
    # 解析查询参数
    query_params = parse_qs(parsed_url.query)
    
    # 修改指定的参数
    for param, value in param_modifications.items():
        query_params[param] = [value]
    
    # 重新编码查询参数
    new_query = urlencode(query_params, doseq=True)
    
    # 重新拼装 URL
    new_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        new_query,
        parsed_url.fragment
    ))
    
    return new_url
# a new class from PlaywrightBrowserPlugin
class MyBrowserPlugin(PlaywrightBrowserPlugin):
    def __init__(self, storage_state, **kwargs):
        super().__init__(**kwargs)
        self._storage_state = storage_state

    @override
    async def new_browser(self) -> PlaywrightBrowserController:
        if not self._playwright:
            raise RuntimeError('Playwright browser plugin is not initialized.')

        if self._browser_type == 'chromium':
            browser = await self._playwright.chromium.launch(**self._browser_options)
        elif self._browser_type == 'firefox':
            browser = await self._playwright.firefox.launch(**self._browser_options)
        elif self._browser_type == 'webkit':
            browser = await self._playwright.webkit.launch(**self._browser_options)
        else:
            raise ValueError(f'Invalid browser type: {self._browser_type}')

        return MyBrowserController(
            self._storage_state,
            browser,
            max_open_pages_per_browser=self._max_open_pages_per_browser,
        )

# a new class from PlaywrightBrowserController
class MyBrowserController(PlaywrightBrowserController):
    def __init__(self, storage_state, browser: Browser, **kwargs):
        super().__init__(browser, **kwargs)
        self._storage_state = storage_state
    @override
    async def new_page(
        self,
        page_options: Mapping[str, Any] | None = None,
        proxy_info: ProxyInfo | None = None,
    ) -> Page:
        if not self._browser_context:
            self._browser_context = await self._create_browser_context_with_state(self._storage_state, proxy_info)

        if not self.has_free_capacity:
            raise ValueError('Cannot open more pages in this browser.')

        page_options = dict(page_options) if page_options else {}
        page = await self._browser_context.new_page(**page_options)

        # Handle page close event
        page.on(event='close', f=self._on_page_close)

        # Update internal state
        self._pages.append(page)
        self._last_page_opened_at = datetime.now(timezone.utc)

        return page
    async def _create_browser_context_with_state(self, storage_state, proxy_info: ProxyInfo | None = None) -> BrowserContext:
        """Create a new browser context with the specified proxy settings."""
        if self._header_generator:
            common_headers = self._header_generator.get_common_headers()
            sec_ch_ua_headers = self._header_generator.get_sec_ch_ua_headers(browser_type=self.browser_type)
            user_agent_header = self._header_generator.get_user_agent_header(browser_type=self.browser_type)
            extra_http_headers = dict(common_headers | sec_ch_ua_headers | user_agent_header)
            user_agent = user_agent_header.get('User-Agent')
        else:
            extra_http_headers = None
            user_agent = None

        proxy = (
            ProxySettings(
                server=f'{proxy_info.scheme}://{proxy_info.hostname}:{proxy_info.port}',
                username=proxy_info.username,
                password=proxy_info.password,
            )
            if proxy_info
            else None
        )

        context = await self._browser.new_context(
            storage_state=storage_state,
            user_agent=user_agent,
            extra_http_headers=extra_http_headers,
            proxy=proxy,
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return context

async def main() -> None:
    # 初始化爬虫
    browser_pool = BrowserPool(plugins=[MyBrowserPlugin(storage_state='state.json', browser_options={"headless":False} )])
    crawler = PlaywrightCrawler(browser_pool=browser_pool, max_requests_per_crawl=200)

    # Define the default request handler, which will be called for every request.
    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        context.log.info(f'Processing {context.request.url} ...')
        #await context.response.body()
        json_data = await context.page.locator('pre').text_content()
        # Extract data from the page.
        data = {
            'url': context.request.url,
            'title': await context.page.title(),
            'response': json_data #await context.page.content() #(await context.response.text()),
        }

        # Push the extracted data to the default dataset.
        await context.push_data(data, dataset_name='TSLA_Crawl_Test')

        # convert 'response' to json object
        #print(f'data is {data}')
        response_json = json.loads(data['response'])
        parsed_url = urlparse(context.request.url)
        query_params = parse_qs(parsed_url.query)
        page_value = query_params.get('page', [None])[0]
        context.log.info(f'Page value is {page_value}, and max page is {response_json["maxPage"]} ...')
        if int(page_value) == response_json["maxPage"] - 1 :
            context.log.info(f'Exit! Page value is {page_value}, and max page is {response_json["maxPage"]} ...')
            return 
        # 替换url参数
        param_modifications = {
            'page': int(page_value) + 1
        }
        new_url = modify_url_params(context.request.url, param_modifications)
        # sleep 5 seconds
        await asyncio.sleep(5)
        await context.add_requests([new_url])
        # # 解析发帖内容
        # posts = []
        # for post in context.soup.select('.article__bd'):
        #     post_data = {
        #         'url': context.request.url,
        #         'title': post.find('a', class_='article__title').text.strip(),
        #         'content': post.find('div', class_='article__content').text.strip(),
        #         'author': post.find('span', class_='user__name').text.strip(),
        #         'time': post.find('span', class_='time').text.strip(),
        #     }
        #     posts.append(post_data)
        
        # # 存储提取的数据
        # await context.push_data(posts)
        
        # # 从当前页面提取链接并添加到爬虫队列
        # next_page_link = context.soup.select_one('.next')
        # if next_page_link and 'href' in next_page_link.attrs:
        #     next_page_url = f"https://xueqiu.com{next_page_link['href']}"
        #     await context.enqueue_links([next_page_url])

    # 使用 Playwright 恢复上下文
    from playwright.async_api import async_playwright

    # async with async_playwright() as p:
    #     with open('state.json', 'r', encoding='utf-8') as file:
    #         state_dict = json.load(file)

    #     print(f'state is {state_dict}')
    #     browser = await p.chromium.launch(headless=False)
        
    #     context = await browser.new_context(storage_state='state.json')
    #     page = await context.new_page()
    #     # read local file  'state.json' to dict
        

    #     # 导航到目标页面
    #     await page.goto('https://xueqiu.com/query/v1/symbol/search/status.json?count=10&comment=0&symbol=TSLA&hl=0&source=all&sort=time&page=5')

    #     # await 50s
    #     await asyncio.sleep(5)
        
    #     # #print(await page.content())
    #     # #await page.wait_for_timeout(10000)
    #     # # 添加第一个 URL 到队列并开始爬虫
    #     # init_request = {
    #     #     'url': 'https://xueqiu.com/query/v1/symbol/search/status.json?count=10&comment=0&symbol=TSLA&hl=0&source=all&sort=time&page=5',
    #     #     'playwright_context': context,
    #     # }

        # # 开始爬虫
    await crawler.run(['https://xueqiu.com/query/v1/symbol/search/status.json?count=10&comment=0&symbol=TSLA&hl=0&source=all&sort=time&page=99'])

if __name__ == '__main__':
    asyncio.run(main())