// Based on the AMap responses observed during the WMT/LYI investigation.
// Fixed dates and temperatures are synthetic; no production key is needed.
const http = require("http");
const cities = {
  "520382": ["仁怀市", "21"],
  "371300": ["临沂市", "18"],
  "深圳": ["深圳市", "28"],
  "北京": ["北京市", "15"],
  "上海": ["上海市", "22"],
  "成都": ["成都市", "20"],
  "遵义": ["遵义市", "19"],
  "西双版纳傣族自治州": ["西双版纳傣族自治州", "26"],
  "抚松县": ["抚松县", "9"],
  "天津": ["天津市", "16"],
};
http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const send = (status, body) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(body));
  };
  if (req.method !== "GET" || url.pathname !== "/v3/weather/weatherInfo") {
    return send(501, { error: "Endpoint not defined" });
  }
  if (url.searchParams.get("key") !== "synthetic-weather-key" || url.searchParams.get("extensions") !== "all") {
    return send(400, { error: "Invalid weather request contract" });
  }
  const city = url.searchParams.get("city");
  if (city === "BUSINESS_ERROR") return send(200, { status: "0", infocode: "10001", info: "INVALID_USER_KEY" });
  if (city === "HTTP_ERROR") return send(503, { error: "Service unavailable" });
  const match = cities[city];
  const forecasts = match ? [{
    city: match[0],
    adcode: city,
    casts: ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"].map((date) => ({
      date, week: "4", dayweather: "晴", nightweather: "多云", daytemp: match[1], nighttemp: "10",
      daywind: "北", nightwind: "北", daypower: "≤3", nightpower: "≤3",
      daytemp_float: match[1], nighttemp_float: "10",
    })),
  }] : [];
  return send(200, { status: "1", infocode: "10000", info: "OK", count: String(forecasts.length), forecasts });
}).listen(process.env.PORT);
