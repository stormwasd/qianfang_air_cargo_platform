// Local regression examples based on the RPA client contract and supplied logs.
// No real booking data or credentials are used.
const http = require("http");
http.createServer(async (req, res) => {
  const path = new URL(req.url, "http://localhost").pathname;
  const send = (status, value) => {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(value));
  };
  if (req.method === "POST" && path === "/openAPI/work-execute/list") {
    let raw = req.body;
    if (raw == null) {
      raw = "";
      for await (const chunk of req) raw += chunk;
    }
    const body = typeof raw === "object" ? raw : JSON.parse(raw);
    const status = body.jobUuid === "failed-job" ? 3 : 5;
    const endTime = body.jobUuid === "missing-end-job" ? null :
      body.jobUuid === "utc-end-job" ? "2026-10-20T10:02:15Z" :
      body.jobUuid === "older-end-job" ? "2026-08-11 09:36:00" : "2026-10-20 18:02:15";
    return send(200, { code: 0, data: { records: [{
      workUuid: "test-work", status, statusDesc: status === 5 ? "运行成功" : "运行失败",
      startTime: "2026-10-20 18:01:58", endTime
    }] } });
  }
  if (req.method === "GET" && path.startsWith("/openAPI/queue/consume/queue-UUID/")) {
    const queue = path.split("/").pop();
    if (queue === "empty") return send(200, { code: 1, msg: "队列已无消息可消费!" });
    if (queue === "product") return send(200, { code: 0, data: { data: JSON.stringify([
      ["SZX-SHA", "1", "10", "0.1", "", "", "", "", "", "READY", "CZ1234", "2026-10-20", "", ""]
    ]) } });
    if (queue === "cargo" || queue === "no-flight") return send(200, { code: 0, data: { data: JSON.stringify([
      ["TEST", "", "", "", "1", "10", queue === "cargo" ? "CZ1234" : "", "test-manifest"]
    ]) } });
  }
  if (req.method === "POST" && path === "/openAPI/v1/queue/delete") {
    return send(200, { code: 0, data: {} });
  }
  return send(501, { code: 1, msg: "Endpoint not modeled by this regression fixture" });
}).listen(process.env.PORT);
