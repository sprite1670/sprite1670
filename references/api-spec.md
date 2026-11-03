# WorkBuddy 签到接口规范

> 逆向自 WorkBuddy 桌面端与金山文档 AirScript 生态实现，非官方文档，可能随版本变动。

## 域名

```
https://copilot.tencent.com
```

## 登录态文件

| 平台 | 路径 |
|---|---|
| Windows | `%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| macOS | `~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info` |

### 结构

```jsonc
{
  "auth": {
    "accessToken":  { "$wbEncrypted": 1, "envelope": "<base64(JSON)>" },
    "refreshToken": { "$wbEncrypted": 1, "envelope": "<base64(JSON)>" }
  }
}
```

### 信封格式

```jsonc
{
  "suite": 1,                    // 固定 1
  "keyId": "9127dea1b44020a7",   // 16 位小写 hex
  "nonce": "<base64>",           // 12 字节 GCM nonce
  "authTag": "<base64>",         // 16 字节 GCM tag
  "ciphertext": "<base64>"       // 密文
}
```

### 密钥派生

```
key    = sha256(atRestSecretKey 的 UTF-8 字节)        // 32 字节
keyId  = sha256(key).hex.slice(0, 16)
```

`atRestSecretKey` 是 44 字符 base64，**只存在于运行中的客户端进程内存**，不落盘、
不在注册表、不在凭据管理器。

### AAD 构造

```javascript
function lenPrefixed(s) {              // 4 字节大端长度 + UTF-8 字节
  const b = Buffer.from(s, 'utf8');
  const l = Buffer.alloc(4); l.writeUInt32BE(b.length);
  return Buffer.concat([l, b]);
}
function u32(v) { const b = Buffer.alloc(4); b.writeUInt32BE(v); return b; }

AAD = Buffer.concat([
  Buffer.from('WB-AAD\0', 'ascii'),    // 5 字节 magic
  Buffer.from([1]),                     // 版本
  lenPrefixed('WBEV1'),                // framing: field
  lenPrefixed('sym-v1'),               // purpose
  u32(1),                              // suite
  lenPrefixed(keyId),                  // 16 hex
  Buffer.from([2]),                    // framing 枚举: field=2
  Buffer.from([0]),                    // sequence 缺省
  Buffer.from([0]),                    // final 缺省
]);
```

framing 枚举：file=1 / field=2 / record=3 / stream=4。

### 解密

```javascript
const d = crypto.createDecipheriv('aes-256-gcm', key, nonce, { authTagLength: 16 });
d.setAAD(aad);
d.setAuthTag(authTag);
const plain = Buffer.concat([d.update(ciphertext), d.final()]).toString('utf8');
```

---

## 接口清单

### 1. 刷新令牌

```
POST /v2/plugin/auth/token/refresh
```

请求头：

| 头 | 值 |
|---|---|
| `Content-Type` | `application/json` |
| `X-Refresh-Token` | 现有 refreshToken |
| `X-Auth-Refresh-Source` | `plugin` |
| `X-Domain` | `copilot.tencent.com` |

Body：`{}`

响应：

```jsonc
{
  "code": 0,
  "msg": "OK",
  "data": {
    "accessToken": "<JWT, ~1566 字符>",
    "refreshToken": "<JWT, ~1567 字符>"
  }
}
```

> 返回的 refreshToken 是**轮换过的新值**，必须回写保存，否则下次用旧的会失败。

### 2. 每日签到

```
POST /v2/billing/meter/daily-checkin
```

请求头：`Authorization: Bearer <accessToken>`

| code | 含义 |
|---|---|
| `0` | 签到成功，`data.credit` 为本次积分（默认 100） |
| `10001` | 今日已签到（幂等，正常返回，非错误） |
| 其他 | 异常，`msg` 带原因 |

### 3. 连签状态

```
POST /v2/billing/meter/checkin-activity-status
```

请求头：`Authorization: Bearer <accessToken>`

```jsonc
{
  "code": 0,
  "data": {
    "active": true,
    "today_checked_in": true,
    "streak_days": 19,
    "daily_credit": 100,
    "today_credit": 100,
    "total_credits": 1900,
    "is_streak_day": false
  }
}
```

---

## 错误码对照

| code / 现象 | 根因 | 处理 |
|---|---|---|
| `12153` `invalid_grant: Session doesn't have required client` | 令牌不属于 plugin client（如来自网页端会话） | 重新 `extract` 取客户端自己的令牌 |
| `0` 但 msg 含"required client" | 同上，检查 `X-Auth-Refresh-Source` 是否为 `plugin` | 修正请求头 |
| 401 | 令牌过期或已轮换 | 用本地最新令牌重试 |
| 解密报 `keyId mismatch` | 密钥已轮换（客户端重启过） | 重启 WorkBuddy 后重新 `extract` |
| 解密报 GCM 认证失败 | AAD 字节不对 | 核对 AAD 构造 |
| `code=10001` | 今日已签 | **不是错误**，属幂等正常返回 |

---

## 金山文档表格约定（AirScript 版）

| 单元格 | 用途 |
|---|---|
| B1 | refresh_token（脚本自动续期并回写） |
| B2 | 最近一次执行结果（带时间戳，脚本写入） |
| B3 | 可选 webhook URL（留空不推送） |
| B4 | 可选兜底通道 JSON（留空关闭） |
| E1..En | 可选的令牌分段区（仅当 B1 为拼接公式时使用，脚本首次运行自动清理） |

Bark webhook：`https://api.day.app/<KEY>`；企微/钉钉机器人：填其 Webhook 地址。

---

## 金山文档 AirScript 开放接口（云端执行）

### 同步执行脚本

```
POST https://www.kdocs.cn/api/v3/ide/file/:file_id/script/:script_id/sync_task
```

| 位置 | 参数 | 说明 |
|---|---|---|
| Header | `Content-Type` | `application/json` |
| Header | `AirScript-Token` | 编辑器「脚本Token」按钮生成（需实名，每用户一个，默认 180 天可延长） |
| path | `file_id` | 表格文件 ID |
| path | `script_id` | 脚本 ID（编辑器左侧栏「更多」→ 复制 webhook 中取） |
| body | `Context.argv` | 运行时参数对象，可选 `force` / `check` |
| body | `Context.sheet_name` | 运行的工作表名 |

请求体：

```json
{"Context": {"argv": {}, "sheet_name": "Sheet1"}}
```

响应：

```jsonc
{
  "data": {
    "result": "……脚本 return 的值……",
    "logs": [{"filename":"","timestamp":"...","level":"info","args":["..."]}]
  },
  "error": "",
  "status": "finished"
}
```

### 异步执行脚本

```
POST https://www.kdocs.cn/api/v3/ide/file/:file_id/script/:script_id/task
```

立即返回 `task_id`，需轮询脚本执行状态接口取日志。适合耗时长的脚本。

### 获取脚本 webhook（编辑器侧）

编辑器左侧脚本栏「更多」→「复制脚本 webhook」，形如：

```
https://www.kdocs.cn/api/v3/ide/file/<file_id>/script/<script_id>/sync_task
```

从中即可取出 `file_id` 与 `script_id`。

### 老版个人开放平台接口（需 access_token）

| 接口 | 用途 |
|---|---|
| `POST /api/v1/openapi/personal/files/:file_token/script` | 创建并执行脚本（异步），用 `taskId` 轮询 |
| `POST /api/v1/openapi/personal/files/:file_token/sync_script` | 同步创建并执行 |
| `GET /api/v1/openapi/personal/personal/script/status` | 查询脚本执行状态 |

### AirScript 平台限制

- 网络请求**只允许域名**，禁止 IP 与端口；超时上限 60 秒；
- 响应体最大 2 MB；
- 必须先在编辑器「服务」里开通对应的高级服务（如「网络API」），否则报"服务未找到"；
- 授权与脚本配置绑定：改动高级服务配置会撤销已有授权，需重新授权。

### 相关文档

- AirScript 总览：https://airsheet.wps.cn/docs/guide/summary.html
- 脚本 Token：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/guide/dbsheet/AirScript/script-token/AirScript-apitoken-instro
- 接口说明：https://open.wps.cn/documents/app-integration-dev/guide/dbsheet/AirScript/script-token/AirScript-apitoken-api
