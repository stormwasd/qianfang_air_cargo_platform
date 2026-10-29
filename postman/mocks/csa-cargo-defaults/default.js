// Synthetic responses based on the existing CSA calculateCharge/createOrder contract.
const http = require("http");
http.createServer(async (req, res) => {
  const send = (status, data) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(data));
  };
  const path = new URL(req.url, "http://localhost").pathname;
  if (req.method !== "POST" || ![
    "/order-center/b2e-order/b2eOrder/calculateCharge",
    "/order-center/b2e-order/b2eOrder/createOrder",
  ].includes(path)) return send(501, { error: "Endpoint not defined" });
  let body = req.body;
  if (body == null) {
    body = "";
    for await (const chunk of req) body += chunk;
  }
  const payload = typeof body === "string" ? JSON.parse(body) : body;
  const shipment = payload.orderInfo && payload.orderInfo.orderShipment;
  const expected = { "普通货物": "3006", "锂电类货物": "3006", "危险品": "3002" };
  if (!shipment || !Object.prototype.hasOwnProperty.call(expected, shipment.shipmentTypeName) ||
      shipment.rateCode !== expected[shipment.shipmentTypeName]) {
    return send(400, { code: "fixture_contract_mismatch", message: "Cargo name/code mismatch" });
  }
  return send(200, { code: "0000", result: {
    extServiceCharges: payload.extServiceCharges,
    observedCargoType: { name: shipment.shipmentTypeName, code: shipment.rateCode },
  } });
}).listen(process.env.PORT || 4903);
