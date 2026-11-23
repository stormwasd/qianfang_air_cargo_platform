"""Run the real weather endpoint and HTTP client against a local AMap simulation."""
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import weather
from app.api.deps import get_current_active_user
from app.core.exceptions import BaseAPIException


@unittest.skipUnless(os.environ.get("AMAP_WEATHER_SIM_ORIGIN"), "Start the local AMap simulation")
class WeatherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = FastAPI()
        self.app.include_router(weather.router, prefix="/api/v1/weather")
        self.app.dependency_overrides[get_current_active_user] = lambda: object()

        @self.app.exception_handler(BaseAPIException)
        async def handle_error(request, exc):
            return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "data": exc.data, "msg": exc.detail})

        endpoint = os.environ["AMAP_WEATHER_SIM_ORIGIN"].rstrip("/") + "/amap/v3/weather/weatherInfo"
        for name, value in (("AMAP_WEATHER_API", endpoint), ("AMAP_KEY", "synthetic-weather-key")):
            patcher = patch.object(weather, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def query(self, airport, date="2026-11-01"):
        return await self.client.get("/api/v1/weather", params={"airport_code": airport, "date": date})

    async def test_reported_airports_and_city_names_select_correct_area_and_date(self):
        groups = (
            (("WMT", "wmt", " WmT ", "遵义茅台", "遵义茅台机场", "仁怀", "仁怀市"), "21"),
            (("LYI", "lyi", " LyI ", "临沂", "临沂市", " 临沂 "), "18"),
        )
        for airports, temperature in groups:
            for airport in airports:
                with self.subTest(airport=airport):
                    response = await self.query(airport)
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    self.assertEqual((body["code"], body["msg"]), (0, "查询成功"))
                    self.assertEqual((body["data"]["date"], body["data"]["daytemp"]), ("2026-11-01", temperature))
                    self.assertEqual(set(body["data"]), set(weather.WeatherResponse.model_fields))

    async def test_existing_airports_special_mappings_and_city_inputs_still_work(self):
        for airport, expected in (("SZX", "28"), ("szx", "28"), ("PEK", "15"), ("PKX", "15"),
                                  ("SHA", "22"), ("PVG", "22"), ("CTU", "20"), ("TFU", "20"),
                                  ("ZYI", "19"), ("JHG", "26"), ("NBS", "9"), ("天津", "16")):
            with self.subTest(airport=airport):
                response = await self.query(airport, "2026-10-29")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["data"]["daytemp"], expected)
                self.assertEqual(response.json()["data"]["date"], "2026-10-29")

    async def test_empty_forecast_and_missing_date_keep_existing_response(self):
        for airport, date in (("UNKNOWN", "2026-11-01"), ("WMT", "2026-12-01"), ("LYI", "2026-10-28")):
            with self.subTest(airport=airport, date=date):
                response = await self.query(airport, date)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"code": 0, "data": None, "msg": "暂无天气预报"})

    async def test_upstream_business_and_http_errors_still_fail(self):
        for city, message in (("BUSINESS_ERROR", "高德天气服务异常: INVALID_USER_KEY"), ("HTTP_ERROR", "请求天气服务失败:")):
            with self.subTest(city=city):
                response = await self.query(city)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.json()["msg"])

    async def test_login_is_still_required(self):
        self.app.dependency_overrides.clear()
        response = await self.query("WMT")
        self.assertIn(response.status_code, (401, 403))

    async def test_query_fields_are_still_required(self):
        for params in ({}, {"airport_code": "WMT"}, {"date": "2026-11-01"}):
            response = await self.client.get("/api/v1/weather", params=params)
            self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
