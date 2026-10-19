// Sanitized examples from the supplied KingGo contract. Local verification only.
const http = require("http");
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const path = url.pathname;
  const send = (status, value) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(value));
  };
  let body = req.body;
  if (body == null) {
    body = "";
    for await (const chunk of req) body += chunk;
  }
  const fields = new URLSearchParams(body);
  if (!url.searchParams.has("oOr6SIhu")) return send(400, { error: "missing signature" });
  if (path === "/flight_info/index/92") {
    const day = fields.get("flightDateStart");
    const page = fields.get("pageNum");
    if (req.method !== "POST" || url.searchParams.get("flag") !== "true" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(day || "") || fields.get("flightDateEnd") !== day ||
        fields.get("flightStatusStrQ") !== "1" || fields.get("areaTypeQ") !== "D" ||
        fields.get("numPerPage") !== "200" || !["1", "2"].includes(page)) {
      return send(400, { error: "flight info contract" });
    }
    const headers = ["序号", "日期", "航班号", "航程", "区域", "起飞", "到达", "实际起飞", "实际到达",
      "飞机号", "机型", "宽/窄", "状态", "总重量", "总体积", "控制重量", "控制体积", "开放重量", "货机", "详情"];
    const cells = [page, day, page === "1" ? "ZH9883" : "ZH9884", "SZX-HGH", "国内", "0930", "1130",
      page === "1" ? "0945" : "", "", "B1234", "738", "窄", "正常", "5000", "30", "4000", "20", "1000", "否", ""];
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead>
      <tbody><tr target="flight_info_id" rel="${page}">${cells.map(c => `<td>${c}</td>`).join("")}</tr></tbody></table>
      <div class="pagination" totalCount="2" numPerPage="1" currentPage="${page}"></div>`);
  }
  if (path.endsWith("agent_order_look/export/125")) {
    if (req.method !== "POST") return send(400, { error: "method" });
    if (fields.get("depCode") !== "SZX" || fields.get("agentCode") !== "SZXFDH" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(fields.get("flightDate") || "") ||
        fields.get("orderType") !== "1" || fields.get("ss") !== "1" || fields.get("nn") !== "0") {
      return send(400, { error: "approval contract" });
    }
    res.writeHead(200, { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    return res.end(Buffer.from("PK\x03\x04sanitized-xlsx", "binary"));
  }
  if (path.endsWith("agent_order_look_wide/export/858")) {
    if (req.method !== "POST") return send(400, { error: "method" });
    if (fields.get("depCode") !== "SZX" || fields.get("agentCode") !== "SZXFDH" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(fields.get("flightDate") || "") ||
        fields.get("ss") !== "1" || fields.get("nn") !== "0" || fields.has("orderType")) {
      return send(400, { error: "wide-body approval contract" });
    }
    res.writeHead(200, { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    return res.end(Buffer.from("PK\x03\x04sanitized-xlsx", "binary"));
  }
  if (path.endsWith("getaway")) {
    if (req.method !== "GET") return send(400, { error: "method" });
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`
      <div id="getWay"><table><tbody>
        <tr><td>1</td><td>ZH9883</td><td>2026-10-19</td><td>0930</td><td>SZX</td><td>杭州</td><td>1</td><td>5.0</td><td>ZH7298</td></tr>
        <tr><td></td><td>合计</td><td></td><td></td><td></td><td></td><td>1</td><td>5.0</td><td></td></tr>
      </tbody></table></div>`);
  }
  if ((path.endsWith("get_awb_no") ? "GET" : "POST") !== req.method) return send(400, { error: "method" });
  if (path.endsWith("check_awb") || path.endsWith("submit_awb")) {
    for (const [key, expected] of Object.entries({
      awbNo: "62046633", takeOffTime: "1525", awbPrefix: "479", billCode: "A1",
      aliasCode: "GEN", formerRate: "5.3", aviationFee: "50", totalFee: "51",
      deliveryFee: "0", oldCabinType: "C", cabinType: "F", cabinTypeName: "F舱",
      carrierCode: "ZH", transNote: "配件", goodsName: "配件", tlicellCellinfos: "[]",
      pieces: "1", chargeWeight: "3", firstAddFee: "", awbType: "",
    })) {
      if (fields.get(key) !== expected) return send(400, { error: `contract mismatch: ${key}` });
    }
    if (!fields.has("agentSname") || !fields.has("operId")) return send(400, { error: "identity" });
    if (path.endsWith("submit_awb") && fields.get("shpInfo") === "FAIL_SUBMIT") {
      res.writeHead(500, { "Content-Type": "text/html" });
      return res.end("<html>Upstream gateway error</html>");
    }
    if (path.endsWith("submit_awb")) {
      const scenario = fields.get("shpInfo");
      if (scenario === "INVALID_JSON") {
        res.writeHead(200, { "Content-Type": "text/html" });
        return res.end("<html>Login required</html>");
      }
      if (scenario === "WRONG_NUMBER" || scenario === "MISSING_ID") {
        return send(200, { retCode: "100", result: {
          awbNo: scenario === "WRONG_NUMBER" ? "00000000" : "62046633",
          awbId: scenario === "MISSING_ID" ? "" : "7220434",
        } });
      }
    }
    if (path.endsWith("check_awb") && fields.get("shpInfo") === "FAIL_CHECK") {
      return send(200, { retCode: "500", msg: "invalid waybill" });
    }
  }
  const responses = {
    "/awb/inland/get_awb_no": { msg: "success", result: "62046633", retCode: "100" },
    "/awb/inland/get_bill_info_by_code": {
      msg: "success",
      result: {
        billId: "295", awbType: "0", billCode: "A1", cabinType: "C",
        dealCode: "GEN", ldcFlag: 0, aliasCode: "GEN", aug: 1, feeModel: 1,
        fastFreightFlag: 0, cabinTypeName: "C舱",
      },
      retCode: "100",
    },
    "/awb/inland/get_flight_no": [{
      takeoffTime: "1525", carrierCode: "ZH", flightNo: "ZH9919",
      flightDate: "2026-10-16", depCode: "SZX", destCode: "TAO",
    }],
    "/awb/inland/computational_costs": {
      aviationFee: 50, aviationRate: 5.3, manageFee: 0, manageRate: 0,
      oilFee: 1, oilRate: 0.25, delayFee: 0, delayRate: 0, deliveryFee: 0,
      deliveryRate: 0, sundryFee: 0, sundryRate: 0, insuranceFee: 0,
      insuranceRate: 0, floorFee: 0, floorRate: 0, insuranceValue: 0,
      otherTotalFee: 1, bargainFlag: 0, freight: 0, agencyFees: 0,
      depOtherFee: 0, firstFee: 0, costAgencyFeesInfos: null,
    },
    "/awb/inland/check_awb": { msg: "检查运单成功", result: "", retCode: "100" },
    "/awb/inland/submit_awb": {
      msg: "提交运单成功", result: { awbStatus: "1", awbNo: "62046633", awbId: "7220434" }, retCode: "100",
    },
  };
  if (!Object.prototype.hasOwnProperty.call(responses, path)) {
    return send(501, { error: "unknown route", path });
  }
  return send(200, responses[path]);
}).listen(process.env.PORT || 4901);
