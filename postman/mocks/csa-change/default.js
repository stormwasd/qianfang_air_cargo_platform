// Synthetic local fixture, based on captured final calls and public super-change JS.
// Never accepts real credentials or proxies to CSA. Does not prove live acceptance.
const http = require("http");
const fixtures = require("./responses.json");
let scenario = "success";
let requests = [];
http.createServer(async (req, res) => {
  const send = (status, data) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(data));
  };
  try {
    const path = new URL(req.url, "http://localhost").pathname;
    if (path === "/__requests" && req.method === "GET") return send(200, requests);
    let body = req.body;
    if (body == null) {
      body = "";
      for await (const chunk of req) body += chunk;
    }
    body = typeof body === "string" ? JSON.parse(body || "{}") : body;
    if (path === "/__reset" && req.method === "POST") {
      scenario = body.scenario;
      requests = [];
      return send(200, { ok: true });
    }
    const name = path.split("/").pop();
    const known = ["forward", "querylivingAnimalProofByorderId", "calculateCWeight", "queryChangePrice", "calculateCharge", "allowedGoodsNameCheck", "checkChange", "createChange"];
    if (req.method !== "POST" || !known.includes(name)) return send(501, { error: "Endpoint not defined" });
    requests.push({ name, body });
    if (["calculateCharge", "checkChange", "createChange"].includes(name)) {
      const order = body.totalOrderDetail?.orderDetailDto;
      if (order?.orderId !== "B-SYNTHETIC" || order.version !== 17 || body.flights?.[0]?.bookId !== 987654) {
        return send(400, { code: "fixture_contract_mismatch", message: "Original order identity lost" });
      }
      if (name === "calculateCharge" && body.changeOtherDto !== null) {
        return send(400, { code: "fixture_contract_mismatch", message: "Calculation carries changeOtherDto" });
      }
    }
    if (name === "createChange") {
      const check = requests[requests.length - 2];
      if (check?.name !== "checkChange" || JSON.stringify(check.body) !== JSON.stringify(body)) {
        return send(400, { code: "fixture_contract_mismatch", message: "Checked and submitted payloads differ" });
      }
      if (scenario === "create-500") return send(500, { error: "Synthetic server failure" });
    }
    const results = {
      ...fixtures, calculateCWeight: { volume: 0.01, cweight: 1 },
      querylivingAnimalProofByorderId: null,
      allowedGoodsNameCheck: { needCheck: true, checkPass: scenario !== "goods-rejected" },
      checkChange: scenario !== "check-rejected",
      createChange: { changeStatus: "F", changeId: "S-SYNTHETIC", errorMsg: null },
    };
    return send(200, { code: "0000", result: results[name] });
  } catch (_err) {
    return send(400, { error: "Malformed synthetic request" });
  }
}).listen(process.env.PORT || 4905);
