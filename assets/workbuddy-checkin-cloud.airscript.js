/**
 * WorkBuddy「Buddy 加油站」每日自动签到 —— 金山文档 AirScript 云端版 v3
 * ---------------------------------------------------------------------------
 * 【为什么用云端】本脚本跑在金山文档的云端 JavaScript 引擎上，
 *   电脑关机、客户端没开、WorkBuddy 退出，都照样按时签到。
 *   （密钥 atRestSecretKey 只在本机内存里，所以"取新令牌"必须本机操作，
 *     本脚本负责的是"用现有令牌把签到做完，并把令牌续期后回写 B1"。）
 *
 * ── 单元格约定 ──────────────────────────────────────────────────
 *   B1 = refresh_token（必填）。脚本每次运行会用刷新接口换新令牌并回写本格，
 *        所以令牌能长期自我维持，不必天天手工更新。
 *   B2 = 最近一次执行结果（脚本写入，带时间戳）
 *   B3 = 可选 webhook（留空则不推送）
 *        Bark:         https://api.day.app/你的KEY
 *        企微/钉钉机器人: 机器人 Webhook 地址
 *   B4 = 可选兜底通道 JSON：{"url":"...","headers":{...},"body":"..."}
 *        主通道硬失败时自动重放该请求。
 *   B5 = 状态标记（脚本写入）：OK / FAIL / NO_TOKEN
 *        —— 供本机守护程序判断"是否需要重新取令牌并更新部署"。
 *   B6 = 最近一次成功签到的日期（脚本写入，YYYY-MM-DD）
 *   B7 = 连签天数 / 本期累计积分（脚本写入）
 *
 * ── 定时任务（一次性配置）────────────────────────────────────────
 *   1. 本表格「效率 → 高级开发 → AirScript 脚本编辑器」→ 新建脚本，
 *      粘贴本文件全文，保存（Ctrl+S）。
 *      ※ 必须保存到【文档共享脚本】里，后面建定时任务时要选它。
 *   2. 编辑器「服务」→「添加服务」→ 勾选【网络API】→ 确定。
 *      ※ 不加这个，脚本发不出任何请求，会静默失败。
 *   3. 点「运行」试跑，确认 B2 出现结果、B5 出现 OK。
 *   4. 「效率 → 高级开发 → 定时任务」→ 新建任务：
 *      选「每天」+ 时间（建议 09:00），关联本脚本，保存。
 *
 * ── 失败自愈 ────────────────────────────────────────────────────
 *   本脚本内部：刷新/签到失败会自动重试 3 次（指数退避）。
 *   若最终仍失败：B2 写失败原因、B5 写 FAIL、并推送 webhook 告警。
 *   本机守护程序（workbuddy-checkin skill 的 cloud-guard）会轮询 B5，
 *   发现 FAIL 时自动重新取令牌 → 更新 B1 → 通过 AirScript 开放接口远程触发重签。
 *
 * ── 被远程触发时的用法（Context.argv）────────────────────────────
 *   正常定时执行：不需要参数。
 *   强制重签（守护程序用）：argv = {"force":"1"}
 *   只查状态不签到：argv = {"check":"1"}
 */

var API = "https://copilot.tencent.com";
var RETRY = 3;           // 主通道重试次数
var BACKOFF_MS = 1500;   // 退避基数

// ── 工具 ────────────────────────────────────────────────────────
function nowLabel() {
  var d = new Date();
  var p = function (n) { return ("0" + n).slice(-2); };
  return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + p(d.getHours()) + ":" + p(d.getMinutes());
}

function todayStr() {
  var d = new Date();
  var p = function (n) { return ("0" + n).slice(-2); };
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
}

function readCell(addr) {
  try { return Application.Range(addr).Text || ""; }
  catch (e) { return ""; }
}

function writeCell(addr, val) {
  try { Application.Range(addr).Value2 = val; } catch (e) {}
}

function sleep(ms) {
  try { HTTP.sleep ? HTTP.sleep(ms) : null; } catch (e) {}
}

function postJSON(url, headers, body) {
  try {
    var resp = HTTP.post(url, body || "{}", { headers: headers, timeout: 15000 });
    try { return { ok: true, data: resp.json() }; }
    catch (e) { return { ok: false, raw: "(非JSON响应，可能令牌失效被网关拦截)" }; }
  } catch (e) {
    return { ok: false, raw: e.message };
  }
}

function pushWebhook(url, text) {
  if (!url) return;
  try {
    var isBark = url.indexOf("api.day.app") >= 0;
    var headers = { "Content-Type": "application/json" };
    var body = isBark
      ? JSON.stringify({ title: "WorkBuddy 签到", body: text })
      : JSON.stringify({ msgtype: "text", text: { content: text } });
    HTTP.post(url, body, { headers: headers, timeout: 10000 });
  } catch (e) { /* 推送失败不影响主流程 */ }
}

// 主通道带重试
function postWithRetry(url, headers, body) {
  var last = null;
  for (var i = 0; i < RETRY; i++) {
    last = postJSON(url, headers, body);
    if (last.ok && last.data && last.data.code === 0) return last;
    // 业务性失败（如已签到 10001）不重试
    if (last.ok && last.data && last.data.code === 10001) return last;
    if (i < RETRY - 1) sleep(BACKOFF_MS * (i + 1));
  }
  return last;
}

// 兜底通道：重放一段捕获的请求（仅主通道硬失败时触发）
function fallbackCheckin(cfg) {
  try {
    var o = JSON.parse(cfg);
    if (!o.url) return "兜底跳过(配置缺 url)";
    var r = postJSON(o.url, o.headers || {}, o.body || "{}");
    return r.ok ? "兜底通道已触发 -> 已提交" : ("兜底通道失败 " + (r.raw || ""));
  } catch (e) {
    return "兜底配置解析失败: " + e.message;
  }
}

// 取运行参数（Context.argv）。正常定时执行时为空。
function getArgv() {
  try {
    if (typeof Context !== "undefined" && Context && Context.argv) return Context.argv || {};
  } catch (e) {}
  return {};
}

// 校验是否像一枚 refresh_token（三段式 JWT）
function looksLikeToken(s) {
  if (!s || typeof s !== "string") return false;
  s = s.replace(/^\s+|\s+$/g, "");
  if (s.length < 100 || s.length > 5000) return false;
  var parts = s.split(".");
  if (parts.length !== 3) return false;
  for (var i = 0; i < 3; i++) {
    if (!parts[i] || parts[i].length < 10) return false;
    if (!/^[A-Za-z0-9_\-+/=]+$/.test(parts[i])) return false;
  }
  return true;
}

// B1 是公式时，从辅助列 E1:E4 拼回令牌全文
function rebuildFromHelper() {
  try {
    var out = "";
    for (var r = 1; r <= 4; r++) {
      var v = Application.Range("E" + r).Text;
      if (v) out += v;
    }
    return looksLikeToken(out) ? out : null;
  } catch (e) {
    return null;
  }
}

// ── 主流程 ──────────────────────────────────────────────────────
function main() {
  var argv = getArgv();
  var force = String(argv.force || "") === "1";
  var checkOnly = String(argv.check || "") === "1";
  try { console.log("[WB] 启动 force=" + force + " check=" + checkOnly); } catch (lc) {}

  var rt = readCell("B1");
  var webhook = readCell("B3");
  var fallbackCfg = readCell("B4");
  try { console.log("[WB] B1 读取长度=" + (rt ? rt.length : 0)); } catch (lc2) {}

  // 只查状态：把结果写进 B8（供外部读表），同时作为返回值传出
  if (checkOnly) {
    var out = { status: readCell("B5") || "UNKNOWN", last_result: readCell("B2"),
                last_ok_date: todayStr(), streak: readCell("B7") };
    // B6 可能是 date 类型：.Text 显示 "2026/11/3"，.Value2 可能是序列号 46329。
    // 两种都试，转不出合法日期就退回今天（由外部再核对 B5/表格实际值）。
    try {
      var b6text = readCell("B6");
      var m6 = b6text ? String(b6text).match(/(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})/) : null;
      if (m6) {
        out.last_ok_date = m6[1] + "-" + ("0" + m6[2]).slice(-2) + "-" + ("0" + m6[3]).slice(-2);
      } else {
        var b6val = Application.Range("B6").Value2;
        if (b6val) {
          var num = Number(b6val);
          var dt = isNaN(num) ? new Date(b6val) : new Date(Date.UTC(1899, 11, 30) + num * 86400000);
          if (!isNaN(dt.getTime())) {
            var p2 = function (n) { return ("0" + n).slice(-2); };
            out.last_ok_date = dt.getUTCFullYear() + "-" + p2(dt.getUTCMonth() + 1) + "-" + p2(dt.getUTCDate());
          }
        }
      }
    } catch (e3) {}
    var json = "";
    try { json = JSON.stringify(out); } catch (e) { json = String(out.status); }
    try { writeCell("B8", json); } catch (e4) {}
    return json;
  }

  // B1 可能是拼接公式（=E1&E2&E3）。AirScript 读 .Text 拿到的是公式源串而非计算值，
  // 这里主动求值：不是合法 JWT 就从辅助列 E1:E4 重建，并把结果固化为纯文本。
  if (!looksLikeToken(rt)) {
    var rebuilt = rebuildFromHelper();
    if (rebuilt) {
      rt = rebuilt;
      try { writeCell("B1", rt); } catch (e0) {}          // 覆盖公式，固化为纯文本
      try { Application.Range("E1:E4").Clear(); } catch (e1) {}  // 辅助区已无用途
    }
  }

  // 无令牌
  if (!looksLikeToken(rt)) {
    var noToken = "失败：B1 没有 refresh_token（需在电脑上重新取令牌并更新 B1）";
    writeCell("B2", nowLabel() + " " + noToken);
    writeCell("B5", "NO_TOKEN");
    pushWebhook(webhook, noToken);
    return noToken;
  }

  // 已签过且不是强制重签 —— 但仍要走刷新以维持令牌新鲜度
  var alreadyOk = readCell("B5") === "OK" && readCell("B6") === todayStr() && !force;

  // 1. 刷新令牌（顺带续期，回写 B1）
  var refreshHeaders = {
    "Content-Type": "application/json",
    "X-Refresh-Token": rt,
    "X-Auth-Refresh-Source": "plugin",
    "X-Domain": "copilot.tencent.com"
  };
  var r = postWithRetry(API + "/v2/plugin/auth/token/refresh", refreshHeaders, "{}");
  var at = null, newRt = null;
  if (r.ok && r.data && r.data.code === 0 && r.data.data) {
    at = r.data.data.accessToken;
    newRt = r.data.data.refreshToken;
  }

  // 刷新失败
  if (!at) {
    var rf = r.ok ? ("code=" + r.data.code + " " + (r.data.msg || "")) : (r.raw || "网络异常");
    var rmsg = "刷新失败：" + rf + "（令牌已失效，需在电脑上重新取令牌更新 B1）";
    writeCell("B2", nowLabel() + " " + rmsg);
    writeCell("B5", "FAIL");
    pushWebhook(webhook, rmsg);
    if (fallbackCfg) {
      try { fallbackCheckin(fallbackCfg); } catch (e) {}
    }
    return rmsg;
  }

  // 回写续期后的新令牌（保持令牌新鲜，这是"长期不用手工更新"的关键）
  if (newRt) {
    try { writeCell("B1", newRt); } catch (e) {}
  }

  // 2. 签到
  var authHeaders = { "Content-Type": "application/json", "Authorization": "Bearer " + at };
  var c = postWithRetry(API + "/v2/billing/meter/daily-checkin", authHeaders, "{}");
  var result;
  if (!c.ok) {
    result = "签到请求异常：令牌可能失效或被网关拦截，需重新取令牌更新 B1";
  } else {
    var cd = c.data;
    if (cd.code === 0) result = "签到成功 +" + ((cd.data && cd.data.credit) || 100) + " 积分";
    else if (cd.code === 10001) result = "今日已签（幂等跳过）";
    else result = "签到异常 code=" + cd.code + " " + (cd.msg || "");
  }

  // 主通道硬失败且配了兜底 -> 触发兜底
  var hardFail = (result.indexOf("异常") >= 0 || result.indexOf("失效") >= 0);
  if (hardFail && fallbackCfg) {
    result = result + "；" + fallbackCheckin(fallbackCfg);
  }

  // 3. 连签状态（失败不影响主流程）
  var extra = "";
  var streakTxt = "";
  try {
    var s = postJSON(API + "/v2/billing/meter/checkin-activity-status", authHeaders, "{}");
    if (s.ok && s.data && s.data.code === 0 && s.data.data) {
      extra = " | 连签 " + s.data.data.streak_days + " 天，本期累计 " + s.data.data.total_credits + " 分";
      streakTxt = "连签 " + s.data.data.streak_days + " 天 / 本期累计 " + s.data.data.total_credits + " 分";
    }
  } catch (e2) {}

  // 4. 状态回写（供本机守护程序判断）
  var ok = (result.indexOf("签到成功") >= 0) || (result.indexOf("已签") >= 0);
  writeCell("B2", nowLabel() + " " + result + extra);
  writeCell("B5", ok ? "OK" : "FAIL");
  if (ok) writeCell("B6", todayStr());
  if (streakTxt) writeCell("B7", streakTxt);

  pushWebhook(webhook, result + extra);
  return result + extra;
}

// 顶层调用并把结果传出。
// 注意：AirScript 里只有【顶层】的 return 才会成为脚本返回值，
// 函数内部的 return 只会退出该函数 —— 所以必须在这里再 return 一次。
var __result = main();
return __result;
