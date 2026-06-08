"""
城市数据处理模块
==========
监听网络请求获取热门城市列表，建立城市名→code 的映射。
"""
from DrissionPage import ChromiumPage

from config.settings import BASE_URL, CITY_API_PATTERN, DEFAULT_CITY
from core.exceptions import CityNotFound
from utils.logger import logger


class CityFetcher:
    """热门城市数据获取器。"""

    def __init__(self, page: ChromiumPage):
        self.page = page
        self._city_dict: dict[str, str] = {}

    # -------- 获取城市数据 --------

    def fetch_hot_cities(self) -> dict[str, str]:
        """
        通过监听网络请求获取热门城市列表。

        流程：
          1. 开始监听 city.json 数据包
          2. 刷新页面触发请求
          3. 解析第一个匹配数据包中的热门城市列表

        Returns:
            dict: {城市名: code}
        """
        self.page.refresh()

        packet = self.page.listen.wait(timeout=10)
        if not packet:
            logger.error("获取城市数据超时")
            return self._city_dict

        body = packet.response.body
        zp_data = body.get("zpData", {})
        city_list = zp_data.get("hotCityList", [])

        self._city_dict = {city["name"]: city["code"] for city in city_list}
        logger.info("获取到 %d 个热门城市", len(self._city_dict))
        for name, code in self._city_dict.items():
            logger.debug("  %s → %s", name, code)

        return self._city_dict

    # -------- 城市查询 --------

    def get_code(self, city_name: str = DEFAULT_CITY) -> str:
        """
        根据城市名获取 code。

        Args:
            city_name: 城市名

        Returns:
            城市 code

        Raises:
            CityNotFound: 城市不在热门列表中
        """
        if not self._city_dict:
            self.fetch_hot_cities()

        code = self._city_dict.get(city_name)
        if code is None:
            raise CityNotFound(city_name, list(self._city_dict.keys()))
        return code

    @property
    def city_names(self) -> list[str]:
        """所有热门城市名称。"""
        return list(self._city_dict.keys())

    @property
    def city_dict(self) -> dict[str, str]:
        """城市名→code 映射。"""
        return self._city_dict
