// Synthetic local fixture, based on captured final calls and public super-change JS.
// Never accepts real credentials or proxies to CSA. Does not prove live acceptance.
const http = require("http");
const fixtures = require("./responses.json");
let scenario = "success";
let requests = [];
let order = structuredClone(fixtures.forward);
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
      order = structuredClone(fixtures.forward);
      if (scenario.startsWith("contacts-") || scenario === "approval-missing-contacts") {
        delete order.totalOrderDetail.orderDetailDto.orderShipmentContact.consigneeMobile;
      }
      return send(200, { ok: true });
    }
    const name = path.split("/").pop();
    const known = ["forward", "saveContactAndLiveAnimals", "querylivingAnimalProofByorderId", "calculateCWeight", "queryChangePrice", "calculateCharge", "allowedGoodsNameCheck", "checkChange", "createChange"];
    if (req.method !== "POST" || !known.includes(name)) return send(501, { error: "Endpoint not defined" });
    requests.push({ name, body });
    if (name === "saveContactAndLiveAnimals") {
      const contact = body.orderShipmentContact;
      const fields = ["shipperName", "shipperMobile", "shipperState", "shipperCity", "shipperDistrict", "shipperAddress", "consigneeName", "consigneeMobile"];
      if (Object.keys(body).length !== 1 || contact?.orderId !== "B-SYNTHETIC" || fields.some(key => !String(contact[key] || "").trim()) ||
          contact.notifyName !== "原通知人" || contact.driverName !== "原司机" || contact.shipperIdno !== "synthetic-id") {
        return send(400, { code: "fixture_contract_mismatch", message: "Saved contact fields lost" });
      }
      if (scenario === "contacts-save-rejected") return send(200, { code: "0001", message: "合成联系人保存拒绝" });
      if (scenario !== "contacts-save-stale") {
        order.totalOrderDetail.orderDetailDto.orderShipmentContact = structuredClone(contact);
        order.totalOrderDetail.orderDetailDto.version = 18;
        order.version = 9;
      }
      return send(200, { code: "0000", result: { MESSAGE: "保存成功" } });
    }
    if (["calculateCharge", "checkChange", "createChange"].includes(name)) {
      const order = body.totalOrderDetail?.orderDetailDto;
      const expectedVersion = ["contacts-missing", "approval-missing-contacts"].includes(scenario) ? 18 : 17;
      if (order?.orderId !== "B-SYNTHETIC" || order.version !== expectedVersion || body.version !== (expectedVersion === 18 ? 9 : 8) || body.flights?.[0]?.bookId !== 987654) {
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
      ...fixtures, forward: order, calculateCWeight: { volume: 0.01, cweight: 1 },
      querylivingAnimalProofByorderId: null,
      allowedGoodsNameCheck: { needCheck: true, checkPass: scenario !== "goods-rejected" },
      checkChange: scenario !== "check-rejected",
      createChange: { changeStatus: "F", changeId: "S-SYNTHETIC", errorMsg: null },
    };
    if (scenario.startsWith("approval-")) {
      results.createChange = { changeStatus: "S", changeStatusName: "待审批", changeId: "S-SYNTHETIC", errorMsg: scenario === "approval-with-error" ? "合成提交错误" : null };
    }
    if (["group-marker-omitted", "tc-string-amount", "required-fee-unpriced"].includes(scenario)) {
      const priced = scenario !== "required-fee-unpriced";
      const tc = scenario === "tc-string-amount";
      const row = {
        serviceMainName: "出港货邮处理费", otherChargeCode: "PU", otherChargeName: "普货",
        changeType: "U", newChecked: "Y", rateUnit: tc ? "TC" : "KG",
        newAmount: tc ? 1 : null, chargeAmount: priced ? 0.45 : null,
      };
      const fee = structuredClone(fixtures.calculateCharge);
      fee.extensionMainCharges = [{ serviceMainName: row.serviceMainName, mandatory: "Y", subCharges: [{ ...row, newAmount: tc ? "1.00" : null }] }];
      fee.extensionCharges = [row];
      results.calculateCharge = fee;
    }
    return send(200, { code: "0000", result: results[name] });
  } catch (_err) {
    return send(400, { error: "Malformed synthetic request" });
  }
}).listen(process.env.PORT || 4905);
