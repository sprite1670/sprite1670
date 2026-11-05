/**
 * WorkBuddy「Buddy 加油站」每日自动签到 —— 金山文档 AirScript 云端版 v4（accessToken 直签）
 * ---------------------------------------------------------------------------
 * 【重要适配说明】
 *   原 v3 依赖 refresh_token 刷新接口做"每次运行自动续期"。但 WorkBuddy 官方已于
 *   2026-10 废弃该接口（POST /v2/plugin/auth/token/refresh 一律返回 code=12153），
 *   原机制已失效。本 v4 改为：B1 直接存 accessToken，跳过刷新，用 Bearer 直接签到。
 *   令牌名义有效期约 30 天；过期后由本机 cloud_guard 守护程序自动从内存取新
 *   accessToken 写回 B1（详见 SKILL.md 的"失败自愈"），实现无人值守闭环。
 *
 * 【为什么用云端】脚本跑在金山文档云端 JS 引擎，电脑关机、客户端没开也能按时签到。
 *   密钥 atRestSecretKey 只在本机内存，所以"取新令牌"必须本机操作；本脚本负责
 *   "用现有 accessToken 把签到做完"，失败标记留给本机 guard 自愈。
 *
 * ── 单元格约定（与 v3 一致）─────────────────────────────────────
 *   B1 = accessToken（必填，直接 Bearer 用，不再刷新）
 *   B2 = 最近一次执行结果（脚本写入，带时间戳）
 *   B3 = 可选 webhook（留空则不推送）
 *   B4 = 可选兜底通道 JSON
 *   B5 = 状态标记（脚本写入）：OK / FAIL / NO_TOKEN
 *   B6 = 最近一次成功签到日期（YYYY-MM-DD）
 *   B7 = 连签天数 / 本期累计积分
 *   B9 = 心跳（每次执行写一行时间戳）
 *
 * ── 定时任务（一次性配置）────────────────────────────────────────
 *   1. 表格「效率 → 高级开发 → AirScript 脚本编辑器」→ 新建脚本，粘贴本文件全文，保存(Ctrl+S)。
 *      ※ 必须保存到【文档共享脚本】。
 *   2. 编辑器「服务」→「添加服务」→ 勾选【网络API】→ 确定（否则静默失败）。
 *   3. 点「运行」试跑，确认 B2 有结果、B5 出现 OK。
 *   4. 「效率 → 高级开发 → 定时任务」→ 新建：每天 09:00，关联本脚本（建议加 21:00 兜底）。
 *
 * ── 失败自愈 ────────────────────────────────────────────────────
 *   本脚本签到失败（令牌失效）时写 B5=FAIL 并推送 webhook；
 *   本机 cloud_guard 轮询到 FAIL → 取新 accessToken → 写回 B1 → 远程重签。
 *
 * ── 被远程触发时的用法（Context.argv）────────────────────────────
 *   正常定时执行：不需要参数。
 *   强制重签（守护程序用）：argv = {"force":"1"}
 *   只查状态不签到：argv = {"check":"1"}
 *   远端写回新令牌并立即签到（守护程序自愈用）：argv = {"settoken":"<新accessToken>"}
 */
// ★ 若 v4 部署早于本版本，请整文件重新粘贴本版，否则 settoken 自愈不会生效。

var API = "https://www.workbuddy.cn";   // 实测接受 accessToken 直签（copilot.tencent.com 的 refresh 已废）
var RETRY = 3;
var BACKOFF_MS = 1500;

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
  try {
    Application.Range(addr).Value2 = val;
    return true;
  } catch (e) {
    try { console.log("[WB] 写入失败 " + addr + ": " + (e && e.message ? e.message : e)); } catch (lg) {}
    return false;
  }
}

function heartbeat(stage) {
  try { writeCell("B9", nowLabel() + " " + stage); } catch (e) {}
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

function postWithRetry(url, headers, body) {
  var last = null;
  for (var i = 0; i < RETRY; i++) {
    last = postJSON(url, headers, body);
    if (last.ok && last.data && last.data.code === 0) return last;
    if (last.ok && last.data && last.data.code === 10001) return last;
    if (i < RETRY - 1) sleep(BACKOFF_MS * (i + 1));
  }
  return last;
}

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

function getArgv() {
  try {
    if (typeof Context !== "undefined" && Context && Context.argv) return Context.argv || {};
  } catch (e) {}
  return {};
}

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

// ── 核心签到逻辑（被正常流程与 settoken 自愈共用）────────────────
function doSign(at, webhook, fallbackCfg) {
  // 1. 直接签到（跳过已废弃的 refresh 续期，accessToken 直签）
  var authHeaders = { "Content-Type": "application/json", "Authorization": "Bearer " + at };
  var c = postWithRetry(API + "/v2/billing/meter/daily-checkin", authHeaders, "{}");
  var result;
  if (!c.ok) {
    result = "签到请求异常：令牌可能失效或被网关拦截，本机 guard 将自动取新令牌写回 B1";
  } else {
    var cd = c.data;
    if (cd.code === 0) result = "签到成功 +" + ((cd.data && cd.data.credit) || 100) + " 积分";
    else if (cd.code === 10001) result = "今日已签（幂等跳过）";
    else result = "签到异常 code=" + cd.code + " " + (cd.msg || "");
  }

  // 硬失败（令牌失效等）→ 标记 FAIL，触发本机 guard 自愈
  var hardFail = (result.indexOf("异常") >= 0 || result.indexOf("失效") >= 0)
                 || (c.ok && c.data && c.data.code !== 0 && c.data.code !== 10001);
  if (hardFail && fallbackCfg) {
    result = result + "；" + fallbackCheckin(fallbackCfg);
  }

  // 2. 连签状态（失败不影响主流程）
  var extra = "";
  var streakTxt = "";
  try {
    var s = postJSON(API + "/v2/billing/meter/checkin-activity-status", authHeaders, "{}");
    if (s.ok && s.data && s.data.code === 0 && s.data.data) {
      extra = " | 连签 " + s.data.data.streak_days + " 天，本期累计 " + s.data.data.total_credits + " 分";
      streakTxt = "连签 " + s.data.data.streak_days + " 天 / 本期累计 " + s.data.data.total_credits + " 分";
    }
  } catch (e2) {}

  // 3. 状态回写
  var ok = (result.indexOf("签到成功") >= 0) || (result.indexOf("已签") >= 0);
  // 硬失败（令牌失效）即便接口返回了非0，也应判为非 OK 让 guard 介入
  if (hardFail) ok = false;
  writeCell("B2", nowLabel() + " " + result + extra);
  writeCell("B5", ok ? "OK" : "FAIL");
  if (ok) writeCell("B6", todayStr());
  if (streakTxt) writeCell("B7", streakTxt);

  pushWebhook(webhook, result + extra);
  return result + extra;
}

// ── 主流程 ──────────────────────────────────────────────────────
function main() {
  var argv = getArgv();
  var force = String(argv.force || "") === "1";
  var checkOnly = String(argv.check || "") === "1";
  var setTok = String(argv.settoken || "");
  try { console.log("[WB] 启动 force=" + force + " check=" + checkOnly + " settoken=" + (setTok ? "yes" : "no")); } catch (lc) {}

  var webhook = readCell("B3");
  var fallbackCfg = readCell("B4");

  // 远端自愈：守护程序把新令牌推给本脚本，直接写回 B1 并立即签到
  if (setTok && looksLikeToken(setTok)) {
    writeCell("B1", setTok);
    try { Application.Range("E1:E4").Clear(); } catch (e1) {}
    heartbeat("settoken写回B1并签到");
    return doSign(setTok, webhook, fallbackCfg);
  }

  // 只查状态
  if (checkOnly) {
    var out = { status: readCell("B5") || "UNKNOWN", last_result: readCell("B2"),
                last_ok_date: todayStr(), streak: readCell("B7") };
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

  // B1 可能是拼接公式（=E1&E2&E3）：主动求值，不是合法 JWT 就从辅助列 E1:E4 重建并固化
  var at = readCell("B1");
  try { console.log("[WB] B1 读取长度=" + (at ? at.length : 0)); } catch (lc2) {}
  heartbeat("启动");

  if (!looksLikeToken(at)) {
    var rebuilt = rebuildFromHelper();
    if (rebuilt) {
      at = rebuilt;
      try { writeCell("B1", at); } catch (e0) {}
      try { Application.Range("E1:E4").Clear(); } catch (e1) {}
    }
  }

  // 无令牌
  if (!looksLikeToken(at)) {
    var noToken = "失败：B1 没有 accessToken（需在本机重新提取 accessToken 并写入 B1）";
    writeCell("B2", nowLabel() + " " + noToken);
    writeCell("B5", "NO_TOKEN");
    pushWebhook(webhook, noToken);
    return noToken;
  }

  return doSign(at, webhook, fallbackCfg);
}

var __result = main();
return __result;
