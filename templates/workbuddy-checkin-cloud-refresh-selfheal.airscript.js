/**
 * WorkBuddy「Buddy 加油站」每日自动签到 —— 金山文档 AirScript 云端版 v5（refresh 自续期 / 真·云端自愈）
 * ---------------------------------------------------------------------------
 * 【设计目标：纯云端自愈，零本机依赖】
 *   脚本跑在金山文档云端引擎，电脑关机、客户端没开也能跑。
 *   B1 存 refreshToken（有效期约 60 天）；每次运行：
 *     1) 用 refreshToken 调刷新接口换出新的 accessToken（30 天）+ 新 refreshToken；
 *     2) 用 accessToken 完成签到；
 *     3) 把新 refreshToken 写回 B1（滚动续期，旧 token 仍可用，不会断）。
 *   只要脚本每天至少跑一次（云端定时任务 08:00/09:00），refreshToken 永远滚不过期，
 *   实现「设置一次、永久自愈」，无需本机守护、无需手动粘令牌。
 *
 * 【为什么不用 accessToken 直签（v4）】
 *   accessToken 仅约 30 天且无法在云端自续期（解密密钥只在本机内存），
 *   到期必须本机介入 —— 违背云端自愈。refreshToken 可在云端自行续期，故 v5 改回 refresh。
 *
 *   注意：实测 refresh 接口可用（code=0，非严格轮换，旧 token 不失效），
 *   之前 v4 笔记里"该接口废弃 code=12153"已不属实，本版据此恢复刷新续期。
 *
 * ── 单元格约定 ────────────────────────────────────────────────
 *   B1 = refreshToken（必填；每次运行后被新值覆盖，请勿手改）
 *   B2 = 最近一次执行结果（带时间戳）
 *   B3 = 可选 webhook（留空不推送）
 *   B4 = 可选兜底通道 JSON
 *   B5 = 状态标记：OK / FAIL / NO_TOKEN
 *   B6 = 最近一次成功签到日期（YYYY-MM-DD）
 *   B7 = 连签天数 / 本期累计积分
 *   B9 = 心跳
 *
 * ── 部署（一次性）──────────────────────────────────────────────
 *   1. 表格「效率 → 高级开发 → AirScript 脚本编辑器」→ 新建脚本，粘贴本文件全文，保存。
 *      ※ 必须保存到【文档共享脚本】。
 *   2. 编辑器「服务」→「添加服务」→ 勾选【网络API】→ 确定（否则静默失败）。
 *   3. 把本机提取的 refreshToken 整段粘到表格 B1（可用 wb_checkin.py extract 后读 out/refreshToken.txt）。
 *   4. 点「运行」试跑，确认 B2 有结果、B5=OK、B1 变成了新的 refreshToken。
 *   5. 「效率 → 高级开发 → 定时任务」→ 新建：每天 08:00（建议加 21:00 兜底），关联本脚本。
 *
 * ★ 关键：本脚本只是"被触发的动作"，真正的定时触发由金山文档的【定时任务】负责。
 *   定时任务若被停用/失效，脚本再正确也不会跑（实测曾停摆：B2 停在 11/8，11/9 起不再触发，
 *   直到手动打开客户端才补领）。请务必保持定时任务启用；若某天 B6 不是当天日期，说明没跑，
 *   需回金山文档检查定时任务状态（可能被平台自动停用，重新启用即可）。
 *
 * ── 被远程触发时的用法（Context.argv）────────────────────────────
 *   正常定时执行：不需要参数。
 *   只查状态不签到：argv = {"check":"1"}
 */
var API = "https://www.workbuddy.cn";
var REFRESH_URL = "https://www.workbuddy.cn/v2/plugin/auth/token/refresh";
var RETRY = 3;
var BACKOFF_MS = 1500;

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
  try { Application.Range(addr).Value2 = val; return true; }
  catch (e) { try { console.log("[WB] 写入失败 " + addr + ": " + (e && e.message ? e.message : e)); } catch (lg) {} return false; }
}
function heartbeat(stage) {
  try { writeCell("B9", nowLabel() + " " + stage); } catch (e) {}
}
function sleep(ms) { try { HTTP.sleep ? HTTP.sleep(ms) : null; } catch (e) {} }

function postJSON(url, headers, body) {
  try {
    var resp = HTTP.post(url, body || "{}", { headers: headers, timeout: 15000 });
    try { return { ok: true, data: resp.json() }; }
    catch (e) { return { ok: false, raw: "(非JSON响应)" }; }
  } catch (e) { return { ok: false, raw: e.message }; }
}

function postWithRetry(url, headers, body) {
  var last = null;
  for (var i = 0; i < RETRY; i++) {
    last = postJSON(url, headers, body);
    if (last.ok && last.data && (last.data.code === 0 || last.data.code === 10001)) return last;
    if (i < RETRY - 1) sleep(BACKOFF_MS * (i + 1));
  }
  return last;
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
  } catch (e) {}
}

function fallbackCheckin(cfg) {
  try {
    var o = JSON.parse(cfg);
    if (!o.url) return "兜底跳过(配置缺 url)";
    var r = postJSON(o.url, o.headers || {}, o.body || "{}");
    return r.ok ? "兜底通道已触发 -> 已提交" : ("兜底通道失败 " + (r.raw || ""));
  } catch (e) { return "兜底配置解析失败: " + e.message; }
}

function getArgv() {
  try { if (typeof Context !== "undefined" && Context && Context.argv) return Context.argv || {}; } catch (e) {}
  return {};
}

function refreshToken(rt) {
  var headers = {
    "Content-Type": "application/json",
    "X-Refresh-Token": rt,
    "X-Auth-Refresh-Source": "plugin",
    "X-Domain": "copilot.tencent.com"
  };
  return postWithRetry(REFRESH_URL, headers, "{}");
}

function doSign(at, webhook, fallbackCfg) {
  var authHeaders = { "Content-Type": "application/json", "Authorization": "Bearer " + at };
  var c = postWithRetry(API + "/v2/billing/meter/daily-checkin", authHeaders, "{}");
  var result;
  if (!c.ok) {
    result = "签到请求异常：令牌可能失效，请检查 B1 的 refreshToken 是否仍有效";
  } else {
    var cd = c.data;
    if (cd.code === 0) result = "签到成功 +" + ((cd.data && cd.data.credit) || 100) + " 积分";
    else if (cd.code === 10001) result = "今日已签（幂等跳过）";
    else result = "签到异常 code=" + cd.code + " " + (cd.msg || "");
  }
  var hardFail = (result.indexOf("异常") >= 0) || (c.ok && c.data && c.data.code !== 0 && c.data.code !== 10001);
  if (hardFail && fallbackCfg) result = result + "；" + fallbackCheckin(fallbackCfg);

  var extra = "", streakTxt = "";
  try {
    var s = postJSON(API + "/v2/billing/meter/checkin-activity-status", authHeaders, "{}");
    if (s.ok && s.data && s.data.code === 0 && s.data.data) {
      extra = " | 连签 " + s.data.data.streak_days + " 天，本期累计 " + s.data.data.total_credits + " 分";
      streakTxt = "连签 " + s.data.data.streak_days + " 天 / 本期累计 " + s.data.data.total_credits + " 分";
    }
  } catch (e2) {}

  var ok = (result.indexOf("签到成功") >= 0) || (result.indexOf("已签") >= 0);
  if (hardFail) ok = false;
  writeCell("B2", nowLabel() + " " + result + extra);
  writeCell("B5", ok ? "OK" : "FAIL");
  if (ok) writeCell("B6", todayStr());
  if (streakTxt) writeCell("B7", streakTxt);
  pushWebhook(webhook, result + extra);
  return { result: result + extra, ok: ok };
}

function main() {
  var argv = getArgv();
  var checkOnly = String(argv.check || "") === "1";
  var webhook = readCell("B3");
  var fallbackCfg = readCell("B4");
  try { console.log("[WB] v5 refresh自续期 启动 check=" + checkOnly); } catch (lc) {}
  heartbeat("启动");

  var rt = readCell("B1");
  if (!rt || rt.length < 100) {
    var noTok = "失败：B1 没有 refreshToken（请把本机提取的 refreshToken 整段粘到 B1）";
    writeCell("B2", nowLabel() + " " + noTok);
    writeCell("B5", "NO_TOKEN");
    pushWebhook(webhook, noTok);
    return noTok;
  }

  // 只查状态
  if (checkOnly) {
    var r = refreshToken(rt);
    var out = { status: "UNKNOWN" };
    if (r.ok && r.data && r.data.code === 0) {
      var at = r.data.data.accessToken;
      var st = postJSON(API + "/v2/billing/meter/checkin-activity-status",
                        { "Content-Type": "application/json", "Authorization": "Bearer " + at }, "{}");
      if (st.ok && st.data && st.data.code === 0 && st.data.data) {
        out = { status: "OK", last_ok_date: todayStr(),
                streak: "连签 " + st.data.data.streak_days + " 天 / 累计 " + st.data.data.total_credits + " 分" };
      }
    } else {
      out = { status: "NO_TOKEN", raw: (r.raw || "") };
    }
    try { writeCell("B8", JSON.stringify(out)); } catch (e4) {}
    return JSON.stringify(out);
  }

  // ① 用 refreshToken 换 accessToken（云端自续期核心）
  var rf = refreshToken(rt);
  if (!rf.ok || !rf.data || rf.data.code !== 0) {
    var rfMsg = "刷新失败 code=" + (rf.data && rf.data.code) + " " + ((rf.data && rf.data.msg) || rf.raw || "");
    writeCell("B2", nowLabel() + " " + rfMsg);
    writeCell("B5", "FAIL");
    pushWebhook(webhook, rfMsg);
    return rfMsg;
  }
  var at = rf.data.data.accessToken;
  var newRT = rf.data.data.refreshToken;
  if (!at) { writeCell("B5", "FAIL"); return "刷新返回缺少 accessToken"; }

  // ② 签到
  var signed = doSign(at, webhook, fallbackCfg);

  // ③ 把新 refreshToken 写回 B1（滚动续期；写失败也不影响本次签到，下次仍可续）
  if (newRT && newRT !== rt) {
    var okWrite = writeCell("B1", newRT);
    if (!okWrite) console.log("[WB] 新 refreshToken 写回 B1 失败，旧值仍可用");
  }

  return signed.result;
}

var __result = main();
return __result;
