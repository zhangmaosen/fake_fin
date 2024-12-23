from __future__ import annotations

import asyncio
import requests
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
import json
from crawlee.browsers import PlaywrightBrowserPlugin, BrowserPool
from crawlee.browsers._playwright_browser_controller import PlaywrightBrowserController
from typing_extensions import override
from crawlee._request import BaseRequestData

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

from playwright.async_api import BrowserContext, Page, ProxySettings
from typing_extensions import override

from crawlee.browsers._base_browser_controller import BaseBrowserController
from crawlee.browsers._types import BrowserType
from crawlee.fingerprint_suite import HeaderGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from crawlee import ConcurrencySettings

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
    concurrency_settings = ConcurrencySettings(
        # Start with 8 concurrent tasks, as long as resources are available.
        desired_concurrency=5,
        # Maintain a minimum of 5 concurrent tasks to ensure steady crawling.
        max_concurrency=5,
        # Limit the maximum number of concurrent tasks to 10 to prevent
        # overloading the system.
        max_tasks_per_minute=40,
    )
    # 初始化爬虫
    browser_pool = BrowserPool(plugins=[MyBrowserPlugin(storage_state='./crawler/state.json', browser_options={"headless":True} )])
    crawler = PlaywrightCrawler(concurrency_settings=concurrency_settings, browser_pool=browser_pool, max_requests_per_crawl=1000)

    # Define the default request handler, which will be called for every request.
    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        context.log.info(f'Processing {context.request.url} ...')


        # Push the extracted data to the default dataset.
        if context.request.label == 'LIST' or context.request.label == None :
            #await context.response.body()
            json_data = await context.page.locator('pre').text_content()
            # Extract data from the page.
            data = {
                'url': context.request.url,
                'title': await context.page.title(),
                'response': json_data, #await context.page.content() #(await context.response.text()),
                'page_num':0
            }
            context.log.info(f'Processing {context.request.url} ...')
            

            # convert 'response' to json object
            #print(f'data is {data}')
            response_json = json.loads(data['response'])
            parsed_url = urlparse(context.request.url)
            query_params = parse_qs(parsed_url.query)
            page_value = query_params.get('pageNumber', [None])[0]
            max_pages = response_json["result"]['pages']

            data['page_num'] = int(page_value)
            await context.push_data(data, dataset_name='JGDY_Crawl_List')

            context.log.info(f'Page value is {page_value}, and max page is {max_pages} ...')
            if int(page_value) == max_pages - 1 :
                context.log.info(f'Exit! Page value is {page_value}, and max page is {max_pages} ...')
                return 
            # 替换url参数
            param_modifications = {
                'pageNumber': int(page_value) + 1
            }
            new_url = modify_url_params(context.request.url, param_modifications)
            # sleep 5 seconds
            #await asyncio.sleep(5)
            request = BaseRequestData.from_url(new_url, user_data={'label':'LIST'})
            await context.add_requests([request])

            for stock in response_json["result"]["data"]:
                SECURITY_CODE = stock['SECURITY_CODE']
                RECEIVE_START_DATE = stock['RECEIVE_START_DATE'].split(' ')[0]
                para = f'{SECURITY_CODE},{RECEIVE_START_DATE}'
                uri = f'https://data.eastmoney.com/jgdy/dyxx/{para}.html'
                request = BaseRequestData.from_url(uri, user_data={'label':'DETAIL'})
                await context.add_requests([request])
                #break
        
        if context.request.label == 'DETAIL':
            context.log.info(f'Processing {context.request.url} ...')
            await context.page.wait_for_selector('#main_content')
            content = await context.page.locator('#main_content').text_content()
            #获得url 最后一个/之后的内容
            SECURITY_CODE = context.request.url.split('/')[-1].split(',')[0]
            data = {
                'url': context.request.url,
                'SECURITY_CODE': SECURITY_CODE,
                'title': await context.page.title(),
                'content': content #await context.page.content() #(await context.response.text()),
            }
            #await asyncio.sleep(2)
            await context.push_data(data, dataset_name='JGDY_Crawl_Detail')
        #context.enqueue_links()


    # 使用 Playwright 恢复上下文
    from playwright.async_api import async_playwright

 
    await crawler.run(['https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=NOTICE_DATE%2CSUM%2CRECEIVE_START_DATE%2CSECURITY_CODE&sortTypes=-1%2C-1%2C-1%2C1&pageSize=50&pageNumber=1&reportName=RPT_ORG_SURVEYNEW&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CNOTICE_DATE%2CRECEIVE_START_DATE%2CRECEIVE_PLACE%2CRECEIVE_WAY_EXPLAIN%2CRECEPTIONIST%2CSUM&quoteColumns=f2~01~SECURITY_CODE~CLOSE_PRICE%2Cf3~01~SECURITY_CODE~CHANGE_RATE&quoteType=0&source=WEB&client=WEB&filter=(NUMBERNEW%3D%221%22)(IS_SOURCE%3D%221%22)(RECEIVE_START_DATE%3E%272021-12-16%27)'])
    #await crawler.export_data_json(path='results.json', ensure_ascii=False)
if __name__ == '__main__':
    asyncio.run(main())