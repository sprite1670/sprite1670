#!/usr/bin/env node
'use strict';
/*
 * WorkBuddy 登录态信封解密器（Node 版，零第三方依赖）
 * ---------------------------------------------------------------
 * WorkBuddy 5.6.2+ 的 auth.* 字段是 AES-256-GCM 加密信封：
 *   { "$wbEncrypted":1, "envelope":"<base64(JSON)>" }
 *   envelope = { suite:1, keyId, nonce, authTag, ciphertext }（均 base64）
 *   密钥 key = sha256(atRestSecretKey 的 UTF-8 字符串)，32 字节
 *   keyId    = sha256(key).hex.slice(0,16)（必须等于 envelope.keyId）
 *   AAD      = buildAuthenticatedContextAad(keyId, suite, {framing:'field'}, 'sym-v1')
 *
 * 用法：
 *   node decrypt_envelope.js --info <workbuddy-desktop.info> --key <base64> --out <目录>
 *   node decrypt_envelope.js --info <...> --key <base64>      # 仅打印到 stdout
 *
 * 密钥来源：运行中的 WorkBuddy 进程内存（见 wb_checkin.py 的 scan 逻辑）。
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ── 常量（与客户端逐字节一致）──
const AAD_MAGIC = Buffer.from('WB-AAD\0', 'ascii');
const FRAMING_CODE = { file: 'WBEF1', field: 'WBEV1', record: 'WBER1', stream: 'WBES1' };
const FRAMING_NUM = { file: 1, field: 2, record: 3, stream: 4 };
const U32_MAX = 4294967295;
const U64_MAX = 18446744073709551615n;

function u32(v) {
  if (!Number.isSafeInteger(v) || v < 0 || v > U32_MAX) throw new RangeError('u32 out of range');
  const b = Buffer.allocUnsafe(4);
  b.writeUInt32BE(v);
  return b;
}

function lenPrefixed(s) {
  const b = Buffer.from(s, 'utf8');
  if (b.length === 0 || b.length > U32_MAX) throw new RangeError('bad length');
  return Buffer.concat([u32(b.length), b]);
}

function buildAuthenticatedContextAad(keyId, suite, ctx, r = 'sym-v1') {
  if (!/^[0-9a-f]{16}$/.test(keyId)) throw new TypeError('keyId must be 16 lowercase hex');
  if (ctx.purpose !== undefined || ctx.resourceId !== undefined || ctx.fieldPath !== undefined) {
    throw new TypeError('sym-v1 context must not carry purpose/resourceId/fieldPath');
  }
  if (ctx.framing === 'file' || ctx.framing === 'field') {
    if (ctx.sequence !== undefined || ctx.final !== undefined) {
      throw new TypeError('sym-v1 whole-value context must not carry sequence/final');
    }
  } else if (ctx.framing === 'record') {
    if (typeof ctx.sequence !== 'bigint' || ctx.final !== undefined) {
      throw new TypeError('record context requires bigint sequence');
    }
  } else if (ctx.framing === 'stream') {
    if (typeof ctx.sequence !== 'bigint' || typeof ctx.final !== 'boolean') {
      throw new TypeError('stream context requires bigint sequence and boolean final');
    }
  } else {
    throw new Error('unsupported framing: ' + String(ctx.framing));
  }
  if (r !== 'sym-v1') throw new Error('only sym-v1 supported');
  return Buffer.concat([
    AAD_MAGIC,
    Buffer.from([1]),
    lenPrefixed(FRAMING_CODE[ctx.framing]),
    lenPrefixed(r),
    u32(suite),
    lenPrefixed(keyId),
    Buffer.from([FRAMING_NUM[ctx.framing]]),
    ctx.sequence !== undefined
      ? Buffer.concat([Buffer.from([1]), Buffer.from('0'.repeat(16), 'hex')])
      : Buffer.from([0]),
    Buffer.from([ctx.final === undefined ? 0 : (ctx.final ? 2 : 1)]),
  ]);
}

function deriveKeyId(key) {
  if (key.byteLength !== 32) throw new Error('normalized at-rest key must be 32 bytes');
  return crypto.createHash('sha256').update(key).digest('hex').slice(0, 16);
}

function normalizeAtRestKeyPayload(atRestSecretKey) {
  const key = crypto.createHash('sha256').update(atRestSecretKey, 'utf8').digest();
  return { key, keyId: deriveKeyId(key) };
}

function openField(env, key, keyId) {
  if (env.keyId !== keyId) throw new Error(`keyId mismatch: envelope=${env.keyId} derived=${keyId}`);
  if (env.suite !== 1) throw new Error('unsupported suite: ' + env.suite);
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm', key, Buffer.from(env.nonce, 'base64'), { authTagLength: 16 },
  );
  decipher.setAAD(buildAuthenticatedContextAad(env.keyId, env.suite, { framing: 'field' }, 'sym-v1'));
  decipher.setAuthTag(Buffer.from(env.authTag, 'base64'));
  return Buffer.concat([
    decipher.update(Buffer.from(env.ciphertext, 'base64')),
    decipher.final(),
  ]).toString('utf8');
}

function decryptEnvelopeField(fieldObj, key, keyId) {
  if (!fieldObj || fieldObj.$wbEncrypted !== 1 || !fieldObj.envelope) {
    throw new Error('not a $wbEncrypted field');
  }
  const env = JSON.parse(Buffer.from(fieldObj.envelope, 'base64').toString('utf8'));
  return openField(env, key, keyId);
}

function main() {
  const argv = process.argv.slice(2);
  const get = (name) => {
    const i = argv.indexOf(name);
    return i >= 0 ? argv[i + 1] : null;
  };
  const infoPath = get('--info') || path.join(
    process.env.LOCALAPPDATA || '',
    'CodeBuddyExtension', 'Data', 'Public', 'auth', 'workbuddy-desktop.info',
  );
  const keyArg = get('--key');
  const outDir = get('--out');

  if (!keyArg) {
    console.error('[!] 缺少 --key <atRestSecretKey-base64>');
    process.exit(2);
  }
  if (!fs.existsSync(infoPath)) {
    console.error('[!] 找不到登录态文件:', infoPath);
    process.exit(3);
  }

  const info = JSON.parse(fs.readFileSync(infoPath, 'utf8'));
  const auth = info.auth || {};
  const { key, keyId } = normalizeAtRestKeyPayload(keyArg.trim());
  console.error('[*] derived keyId:', keyId);

  const result = {};
  for (const name of ['accessToken', 'refreshToken', 'idToken']) {
    if (auth[name] && auth[name].$wbEncrypted === 1) {
      try {
        result[name] = decryptEnvelopeField(auth[name], key, keyId);
        console.error(`[+] ${name} 解密成功 (${result[name].length} 字符)`);
      } catch (e) {
        console.error(`[!] ${name} 解密失败: ${e.message}`);
      }
    }
  }

  if (outDir) {
    fs.mkdirSync(outDir, { recursive: true });
    for (const [k, v] of Object.entries(result)) {
      fs.writeFileSync(path.join(outDir, k + '.txt'), v, 'utf8');
    }
    console.error('[*] 已写出到', outDir);
  } else {
    for (const [k, v] of Object.entries(result)) {
      console.log(`===== ${k} =====`);
      console.log(v);
    }
  }

  if (!result.refreshToken) {
    console.error('[!] 未解出 refreshToken。');
    process.exit(4);
  }
}

if (require.main === module) main();
module.exports = {
  buildAuthenticatedContextAad, normalizeAtRestKeyPayload, openField,
  decryptEnvelopeField, deriveKeyId,
};
