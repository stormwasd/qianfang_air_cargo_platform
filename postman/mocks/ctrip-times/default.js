// Synthetic examples derived from app/utils/ctrip_client.py and its regression tests.
// Local verification only; this is not a provider-owned mock.
const http = require("http");
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const send = (status, data) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(data));
  };
  if (req.method === "GET" && url.pathname === "/restapi/soa2/10290/createclientid") {
    return send(200, { ClientID: "local-ctrip-flight-guid" });
  }
  if (req.method === "POST" && url.pathname === "/restapi/soa2/14566/FlightVarDetailSearchV2") {
    let raw = req.body;
    if (raw == null) {
      raw = "";
      for await (const chunk of req) raw += chunk;
    }
    const body = typeof raw === "object" ? raw : JSON.parse(raw);
    const item = body.fltItem || {};
    if (!/^[A-Z]{3}$/.test(item.dPort || "") || !/^[A-Z]{3}$/.test(item.aPort || "") ||
        !/^[A-Z0-9]{2}\d{1,4}$/.test(item.fltno || "") ||
        !/^\d{4}-\d{2}-\d{2}$/.test(item.queryDate || "")) {
      return send(400, { error: "Ctrip flight/date/airport-code contract" });
    }
    if (item.fltno === "ZH9999") {
      return send(503, { error: "Synthetic upstream unavailable" });
    }
    return send(200, {
      ResponseStatus: { Ack: "Success" },
      detailItem: { basicItemInfo: { dItemInfo: { dateTimeForRecord: {
        plannedDateTime: `${item.queryDate} 10:00:00`,
        ReadyDateTime: null,
        actualDateTime: `${item.queryDate} 10:10:00`,
      } } } },
    });
  }
  return send(501, { error: "Endpoint not modeled by the flight-times fixture" });
}).listen(process.env.PORT);
