/**
 * WorkBuddy「Buddy 加油站」每日自动签到 —— 金山文档 AirScript 版 v2
 * 增强：令牌自续期 + 已签幂等 + 可选 webhook 推送 + 可选兜底通道
 *
 * ── 单元格约定 ───────────────────────────────────────────
 *   B1 = refresh_token（每次运行自动续期并回写，旧令牌兜底）
 *   B2 = 最近一次执行结果（带时间戳，脚本写入）
 *   B3 = 可选 webhook（留空则不推送）
 *         Bark:    https://api.day.app/你的KEY
 *         企微/钉钉机器人: 其 Webhook 地址
 *   B4 = 可选兜底通道（留空则关闭）
 *        填一段 JSON: {"url":"...","headers":{...},"body":"..."}
 *        当主通道(refresh/checkin)硬失败时自动重放该请求。
 *   E1:E4 = 可选的令牌分段存放区（仅当 B1 是拼接公式时使用）。
 *        脚本首次运行会自动把 B1 还原成纯文本并清空本区域，之后可忽略。
 *
 * ── 部署（一次性，约 3 分钟）─────────────────────────────
 * 1. 取 refresh_token：WorkBuddy 电脑客户端 → 新建任务 → 发提示词让其读取
 *    %LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info
 *    只提取 auth.refreshToken 字段值（约 700 字符，完整复制，别漏字符）。
 * 2. 金山文档(kdocs.cn) 新建空白表格 → B1 粘令牌，B2/B3/B4 留空。
 * 3. 效率 → 高级开发 → AirScript 脚本编辑器 → 新建脚本，整段粘贴本代码，保存。
 *    编辑器「服务」→ 添加服务 → 勾选「网络API」。点运行试跑，B2 出结果即成功。
 * 4. 效率 → 高级开发 → 定时任务 → 选本脚本，每天 09:00（建议再加 21:00 兜底）。
 *    ※ 这是金山文档云端自带的定时器，不是本机 cron，符合“不要定时任务”要求。
 *
 * 注：接口逆向自 WorkBuddy 桌面端，非官方文档，可能随版本变动。
 */

var API = "https://copilot.tencent.com";

function postJSON(url, headers, body) {
  try {
    var resp = HTTP.post(url, body || "{}", { headers: headers, timeout: 15000 });
    try { return { ok: true, data: resp.json() }; }
    catch (e) { return { ok: false, raw: "(非JSON响应，可能令牌失效被网关拦截)" }; }
  } catch (e) {
    return { ok: false, raw: e.message };
  }
}

function nowLabel() {
  var d = new Date();
  var p = function (n) { return ("0" + n).slice(-2); };
  return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + p(d.getHours()) + ":" + p(d.getMinutes());
}

// 可选 webhook 推送（Bark 用 POST JSON；企微/钉钉机器人用 text 结构）
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

// 可选兜底通道：重放一段捕获的请求（仅主通道硬失败时触发）
function fallbackCheckin(cfg) {
  try {
    var o = JSON.parse(cfg);
    if (!o.url) return "兜底跳过(配置缺 url)";
    var r = postJSON(o.url, o.headers || {}, o.body || "{}");
    return "兜底通道已触发 -> " + (r.ok ? "已提交" : "失败 " + (r.raw || ""));
  } catch (e) {
    return "兜底配置解析失败: " + e.message;
  }
}

// 校验是否像一枚 refresh_token（三段 JWT：两个点分隔的 base64url 段）
function looksLikeToken(s) {
  if (!s || typeof s !== "string") return false;
  s = s.replace(/^\s+|\s+$/g, "");
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

function main() {
  var rt = Application.Range("B1").Text;
  var webhook = Application.Range("B3").Text;
  var fallbackCfg = Application.Range("B4").Text;

  // B1 可能是拼接公式（=E1&E2&E3&E4）。AirScript 读 .Text 会拿到公式源串而非计算值，
  // 这里主动求值：若 .Text 不是合法 JWT（三段、含两个点），则尝试从辅助列拼回。
  if (!looksLikeToken(rt)) {
    var rebuilt = rebuildFromHelper();
    if (rebuilt) {
      rt = rebuilt;
      // 固化为纯文本：把算出的令牌写回 B1（覆盖公式），并清空辅助列
      try { Application.Range("B1").Value2 = rt; } catch (e) {}
      try { Application.Range("E1:E4").Clear(); } catch (e2) {}
    }
  }

  if (!rt || !looksLikeToken(rt)) {
    var noToken = "失败：B1 没有 refresh_token";
    Application.Range("B2").Value2 = nowLabel() + " " + noToken;
    pushWebhook(webhook, noToken);
    return;
  }

  // 1. 刷新令牌
  var refreshHeaders = {
    "Content-Type": "application/json",
    "X-Refresh-Token": rt,
    "X-Auth-Refresh-Source": "plugin",
    "X-Domain": "copilot.tencent.com"
  };
  var r = postJSON(API + "/v2/plugin/auth/token/refresh", refreshHeaders, "{}");
  var at = null, newRt = null;
  if (r.ok && r.data && r.data.code === 0 && r.data.data) {
    at = r.data.data.accessToken;
    newRt = r.data.data.refreshToken;
  }

  // 刷新失败：尝试兜底通道
  if (!at) {
    var rf = r.ok ? ("code=" + r.data.code + " " + (r.data.msg || "")) : (r.raw || "网络异常");
    var rmsg = fallbackCfg ? ("刷新失败(" + rf + ")；" + fallbackCheckin(fallbackCfg))
                          : ("刷新失败：" + rf + "（需重新取令牌填入 B1）");
    Application.Range("B2").Value2 = nowLabel() + " " + rmsg;
    pushWebhook(webhook, rmsg);
    return;
  }

  // 自续期：回写新令牌（写失败则保留旧令牌兜底）
  if (newRt) { try { Application.Range("B1").Value2 = newRt; } catch (e) {} }

  // 2. 签到（幂等）
  var authHeaders = { "Content-Type": "application/json", "Authorization": "Bearer " + at };
  var c = postJSON(API + "/v2/billing/meter/daily-checkin", authHeaders, "{}");
  var result;
  if (!c.ok) {
    result = "签到请求异常：令牌可能失效或被网关拦截，请重新取令牌填入 B1";
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
  try {
    var s = postJSON(API + "/v2/billing/meter/checkin-activity-status", authHeaders, "{}");
    if (s.ok && s.data && s.data.code === 0 && s.data.data) {
      extra = " | 连签 " + s.data.data.streak_days + " 天，本期累计 " + s.data.data.total_credits + " 分";
    }
  } catch (e2) {}

  var line = nowLabel() + " " + result + extra;
  Application.Range("B2").Value2 = line;
  pushWebhook(webhook, result + extra);
}

main();
