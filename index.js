/**
 * dsh-sim-telemetry —— F1 25 UDP 遥测采集/分析插件（v4）
 *
 * v4 新增：
 *  - UDP 端口可配（默认 20777，和 F1 25「设置 → Telemetry → UDP Port」保持一致）
 *  - Python 环境自动检测：要求 >= 3.10，No more 硬编码某个人的安装路径
 *  - 设置页可一键安装 Python 3.12（winget 优先，失败退回 python.org 官方静默安装）
 *  - 可一键补 Pillow（画图才需要）
 *
 * 原则：加载阶段绝不抛错。所有异常写进 <data>/debug.log，最多次功能缺失，不会把宿主带崩。
 */
import { spawn, execFile } from "node:child_process";
import { appendFileSync, closeSync, createWriteStream, existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import { defineTool } from "@deepseek-ai/dsh-tools";

export const name = "sim-telemetry";
export const inject = ["tools", "webServer"];

const PY_DIR = fileURLToPath(new URL("./lib/py/", import.meta.url));
const DEFAULTS = { enabled: true, durationSec: 900, autoReportLaps: 0, pythonPath: "", udpPort: 20777 };
const MIN_MINOR = 10; // 需要 Python 3.10+
const PY_INSTALL_VERSION = "3.12.10";
const PY_INSTALL_URL = `https://www.python.org/ftp/python/${PY_INSTALL_VERSION}/python-${PY_INSTALL_VERSION}-amd64.exe`;
const state = { proc: null, startedAt: 0, install: null, deps: null };
let cfg = { ...DEFAULTS };
let probe = { running: false, done: false, info: null };

function dataDir() {
  const home = process.env.DSH_HOME || join(homedir(), ".dsh");
  const dir = join(home, "sim-telemetry");
  try { mkdirSync(dir, { recursive: true }); } catch { /* 忽略 */ }
  return dir;
}

function dbg(msg) {
  try { appendFileSync(join(dataDir(), "debug.log"), `${new Date().toISOString()} ${msg}\n`); } catch { /* 忽略 */ }
}

function execFileAsync(file, args, options = {}) {
  return new Promise((resolve) => {
    try {
      execFile(file, args, {
        timeout: 15000, windowsHide: true, maxBuffer: 4 * 1024 * 1024, encoding: "utf8", ...options,
      }, (err, stdout, stderr) => {
        resolve({ err: err || null, stdout: String(stdout || ""), stderr: String(stderr || "") });
      });
    } catch (err) {
      resolve({ err, stdout: "", stderr: "" });
    }
  });
}

/** 列出所有可能藏 Python 的地方（不用硬编码任何人的用户名） */
function buildCandidates() {
  const out = [];
  const push = (label, exe, args) => { if (exe) out.push({ label, exe, args: args || [] }); };
  if (cfg.pythonPath) push("设置里的路径", cfg.pythonPath, []);
  if (process.env.SIM_PYTHON) push("SIM_PYTHON", process.env.SIM_PYTHON, []);
  // Windows py launcher 按版本选
  for (const v of ["3.13", "3.12", "3.11", "3.10"]) push(`py -${v}`, "py", [`-${v}`]);
  // 每用户安装目录
  const local = process.env.LOCALAPPDATA || "";
  for (const v of ["313", "312", "311", "310"]) {
    push(`Python${v}(用户目录)`, local ? join(local, "Programs", "Python", `Python${v}`, "python.exe") : "", []);
  }
  // 全用户安装目录
  for (const v of ["313", "312", "311", "310"]) push(`C:\\Python${v}`, `C:\\Python${v}\\python.exe`, []);
  push("PATH python", "python", []);
  push("PATH python3", "python3", []);
  return out;
}

/** 探测一个候选：返回 {exe, args, version} 或 null */
async function probeOne(c) {
  if (c.exe.includes("\\") && !existsSync(c.exe)) return null;
  const r = await execFileAsync(c.exe, [...c.args, "-c", "import sys;sys.stdout.write('%d.%d.%d'%sys.version_info[:3])"], { timeout: 6000 });
  if (r.err) return null;
  const v = String(r.stdout || "").trim().split(/\s+/).pop() || "";
  const m = v.match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!m) return null;
  if (Number(m[1]) !== 3 || Number(m[2]) < MIN_MINOR) return null;
  return { exe: c.exe, args: c.args, version: v };
}

async function detectPythonAsync() {
  for (const c of buildCandidates()) {
    try {
      if (c.exe.includes("\\") && !existsSync(c.exe)) continue;
      const hit = await probeOne(c);
      if (!hit) continue;
      // 顺手看 Pillow 在不在（只有画图才用）
      let pillowOk = false;
      const p = await execFileAsync(hit.exe, [...hit.args, "-c", "import sys, PIL;sys.stdout.write(PIL.__version__)"], { timeout: 8000 });
      if (!p.err && String(p.stdout || "").trim()) pillowOk = true;
      return { exe: hit.exe, args: hit.args, version: hit.version, pythonOk: true, pillowOk, checkedAt: Date.now() };
    } catch { /* 试下一个 */ }
  }
  return { exe: null, args: [], version: "", pythonOk: false, pillowOk: false, checkedAt: Date.now() };
}

function startProbe() {
  if (probe.running) return;
  probe.running = true;
  detectPythonAsync().then((info) => {
    probe = { running: false, done: true, info };
    dbg(`python 探测：${info.pythonOk ? info.exe + " " + info.version : "未找到 3.10+"}`);
  }).catch((err) => {
    probe = { running: false, done: true, info: null };
    dbg(`python 探测异常：${(err && err.message) || err}`);
  });
}

/** 同步读取探测结果（不触发探测），给不需要等待的场景用 */
function pythonInfo() {
  return probe.info && probe.info.pythonOk ? probe.info : null;
}

/**
 * 等 Python 探测完成再返回结果。
 *
 * ⚠️ 以前是 currentPython()：`if (!probe.done) startProbe(); return probe.info && ...`
 * —— 探测是异步的，函数却立刻读 `probe.info`，**第一次调用必然拿到 null**，
 * 表现就是重启后第一次 `telemetry_start` 报「没有找到 Python 3.10+」，再点一次才好。
 * 改成 async 等待，第一次就能成功。
 */
async function ensurePython() {
  if (!probe.done) {
    if (!probe.running) {
      probe.running = true;
      try {
        const info = await detectPythonAsync();
        probe = { running: false, done: true, info };
        dbg(`python 探测：${info.pythonOk ? info.exe + " " + info.version : "未找到 3.10+"}`);
      } catch (err) {
        probe = { running: false, done: true, info: null };
        dbg(`python 探测异常：${(err && err.message) || err}`);
      }
    } else {
      // 已有探测在进行，等它完成（最多 20 秒）
      await new Promise((resolve) => {
        const t = setInterval(() => {
          if (probe.done) { clearInterval(t); resolve(); }
        }, 150);
        setTimeout(() => { clearInterval(t); resolve(); }, 20000);
      });
    }
  }
  return probe.info && probe.info.pythonOk ? probe.info : null;
}

function readSettings() {
  try { return JSON.parse(readFileSync(join(dataDir(), "settings.json"), "utf8")); } catch { return {}; }
}

function writeSettings(next) {
  try { writeFileSync(join(dataDir(), "settings.json"), JSON.stringify(next, null, 2), "utf8"); } catch { /* 忽略 */ }
}

function pyEnv() {
  return { ...process.env, SIM_DATA_DIR: dataDir(), SIM_UDP_PORT: String(cfg.udpPort || 20777), PYTHONIOENCODING: "utf-8" };
}

async function runPython(script, args = [], timeoutMs = 180000) {
  const info = await ensurePython();
  if (!info) return { ok: false, stdout: "", stderr: "没有找到 Python 3.10+，请到「设置 → 赛车遥测」点一键安装。" };
  return new Promise((resolve) => {
    try {
      execFile(info.exe, [...info.args, join(PY_DIR, script), ...args], {
        env: pyEnv(), timeout: timeoutMs, maxBuffer: 8 * 1024 * 1024, windowsHide: true,
      }, (error, stdout, stderr) => {
        resolve({ ok: !error, stdout: String(stdout || "").trim(), stderr: String(stderr || "").trim().slice(-1200) });
      });
    } catch (err) {
      resolve({ ok: false, stdout: "", stderr: String((err && err.message) || err) });
    }
  });
}

async function startCollect(durationSec) {
  if (state.proc) return { ok: false, error: "已经在采集中" };
  if (cfg.enabled === false) return { ok: false, error: "插件功能已关闭（设置页里打开开关）" };
  const info = await ensurePython();
  if (!info) return { ok: false, error: "没有找到 Python 3.10+，先到设置页点「一键安装 Python」" };
  try {
    const dur = Math.max(30, Math.min(3600, Number(durationSec) || cfg.durationSec || 900));
    // ⚠️ 采集器必须 **detached 启动 + unref**，否则会被宿主回收（2026-10-26 踩到，很隐蔽）：
    //    以前用普通 spawn，子进程挂在 DSH 的进程树上。会话一空闲（工具调用结束后几分钟没人操作），
    //    宿主回收进程树 → 采集器被杀。表现是「启动了、文件建了 0 字节、日志不更新、端口后来空了」，
    //    而且因为 stdio 是 pipe，错误只留在内存里，完全查不到原因。
    //    修法三件事：
    //      1. detached: true + child.unref() —— 独立进程组，宿主管不到它
    //      2. stdio 直接 ignore，日志路径用 SIM_LOG 传给 Python，由它自己写文件
    //         （pipe 会在宿主退出时断掉、裸 fd 在 Windows 上不生效、未打开的 WriteStream 又会被 spawn 拒绝，
    //          三种都不行 —— 2026-10-26 三种都试过，最后走「Python 自己写日志」这条路才稳）
    //      3. 监听 exit 记下退出码 —— 崩溃能定位
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const logPath = join(dataDir(), `collect_${stamp}.log`);
    const child = spawn(info.exe, [...info.args, join(PY_DIR, "collect_f1.py"), String(dur), String(cfg.autoReportLaps || 0)], {
      env: { ...pyEnv(), SIM_LOG: logPath }, windowsHide: true, detached: true, stdio: "ignore",
    });
    child.unref();
    state.proc = child;
    state.logPath = logPath;
    state.startedAt = Date.now();
    child.on("exit", (code) => {
      state.proc = null;
      dbg(`采集进程退出 code=${code} log=${logPath}`);
    });
    return { ok: true, pid: child.pid, durationSec: dur, udpPort: cfg.udpPort || 20777, logFile: logPath };
  } catch (err) {
    return { ok: false, error: String((err && err.message) || err) };
  }
}

function stopCollect() {
  const proc = state.proc;
  if (!proc) return { ok: false, error: "当前没有在采集" };
  try {
    execFile("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { windowsHide: true }, () => {});
  } catch { /* 忽略 */ }
  state.proc = null;
  return { ok: true, pid: proc.pid, seconds: Math.round((Date.now() - state.startedAt) / 1000) };
}

function status() {
  if (!probe.done) startProbe();
  const info = probe.info;
  return {
    ok: true,
    enabled: cfg.enabled !== false,
    durationSec: cfg.durationSec || 900,
    autoReportLaps: cfg.autoReportLaps || 0,
    udpPort: cfg.udpPort || 20777,
    collecting: Boolean(state.proc),
    collectingSeconds: state.proc ? Math.round((Date.now() - state.startedAt) / 1000) : 0,
    dataDir: dataDir(),
    python: info && info.exe ? info.exe : null,
    pythonVersion: info && info.version ? info.version : "",
    pythonOk: info ? Boolean(info.pythonOk) : null,
    pythonChecking: probe.running || !probe.done,
    pillowOk: info ? Boolean(info.pillowOk) : null,
    pythonPath: cfg.pythonPath || "",
    install: state.install,
    deps: state.deps,
  };
}

/** 一键装 Python 3.12：先 winget，失败退回 python.org 官方静默安装 */
function installPython() {
  if (state.install && !state.install.done) return { ok: false, error: "已经在安装中了" };
  state.install = { startedAt: Date.now(), step: "准备中…", done: false, ok: null, log: [] };
  const setStep = (s) => { if (state.install) state.install.step = s; };
  const log = (s) => { if (state.install) state.install.log.push(`${new Date().toLocaleTimeString()} ${s}`); };

  (async () => {
    try {
      setStep("尝试用 winget 安装 Python 3.12（可能需要几分钟）…");
      const w = await execFileAsync("winget", [
        "install", "-e", "--id", "Python.Python.3.12", "--silent",
        "--accept-package-agreements", "--accept-source-agreements", "--scope", "user",
      ], { timeout: 20 * 60 * 1000 });
      log(`winget ${w.err ? "失败：" + String(w.stderr || w.err.message).slice(0, 400) : "成功"}`);

      if (w.err) {
        setStep("winget 没成功，改下 python.org 官方安装包…");
        const res = await fetch(PY_INSTALL_URL);
        if (!res.ok) throw new Error("下载官方安装包失败 HTTP " + res.status);
        const buf = Buffer.from(await res.arrayBuffer());
        const tmp = join(dataDir(), "python-installer.exe");
        writeFileSync(tmp, buf);
        log(`已下载安装包 ${(buf.length / 1024 / 1024).toFixed(1)} MB`);
        setStep("正在静默安装 Python（1-2 分钟）…");
        const r2 = await execFileAsync(tmp, ["/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_pip=1"], { timeout: 20 * 60 * 1000 });
        log(`官方安装包 ${r2.err ? "失败：" + String(r2.stderr || r2.err.message).slice(0, 400) : "成功"}`);
        try { unlinkSync(tmp); } catch { /* 忽略 */ }
      }

      setStep("重新检测 Python 环境…");
      probe = { running: false, done: false, info: null };
      const info = await detectPythonAsync();
      probe = { running: false, done: true, info };
      const ok = Boolean(info.pythonOk);
      state.install = {
        ...state.install, done: true, ok,
        step: ok ? `安装完成：Python ${info.version}` : "安装结束，但还没检测到 Python 3.10+（可以重启 DSH 再试，或手动指定路径）",
      };
      dbg(`installPython 结束 ok=${ok} version=${info.version}`);
    } catch (err) {
      state.install = { ...state.install, done: true, ok: false, step: "安装失败：" + String((err && err.message) || err) };
      dbg(`installPython 异常：${(err && err.message) || err}`);
    }
  })();

  return { ok: true, started: true };
}

/** 装画图要用的 Pillow */
function installDeps() {
  if (state.deps && !state.deps.done) return { ok: false, error: "已经在装了" };
  const info = pythonInfo();
  if (!info) return { ok: false, error: "先装 Python 3.10+ 再装依赖" };
  state.deps = { startedAt: Date.now(), step: "安装 Pillow…", done: false, ok: null };
  execFileAsync(info.exe, [...info.args, "-m", "pip", "install", "--upgrade", "pillow"], { timeout: 10 * 60 * 1000 })
    .then((r) => {
      const ok = !r.err;
      state.deps = { ...state.deps, done: true, ok, step: ok ? "Pillow 已安装" : "安装失败：" + String(r.stderr || r.err.message).slice(0, 300) };
      probe = { running: false, done: true, info: { ...info, pillowOk: ok || info.pillowOk } };
    })
    .catch((err) => {
      state.deps = { ...state.deps, done: true, ok: false, step: "安装失败：" + String((err && err.message) || err) };
    });
  return { ok: true, started: true };
}

function textOutput(_args, value) {
  return [{ type: "text", text: String(value) }];
}

export function apply(ctx, config = {}) {
  try {
    dbg(`apply 进入 register=${Boolean(ctx && ctx.tools && ctx.tools.register)}`);
    cfg = { ...DEFAULTS, ...readSettings(), ...(config && typeof config === "object" ? config : {}) };

    const define = (spec) => defineTool(spec);
    dbg("使用 @deepseek-ai/dsh-tools 的 defineTool");
    if (!ctx.tools || typeof ctx.tools.register !== "function") {
      dbg("ctx.tools.register 不可用：跳过");
      return;
    }

    const register = (spec) => {
      try {
        const tool = define({
          ...spec,
          output: { schema: { type: "string" }, render: textOutput },
          async execute(args) {
            try { return await spec.execute(args || {}); } catch (err) { return `失败：${(err && err.message) || err}`; }
          },
        });
        ctx.tools.register(tool);
        dbg(`工具注册成功：${spec.name}`);
      } catch (err) {
        dbg(`工具注册失败 ${spec.name}：${(err && err.message) || err}`);
      }
    };

    register({
      name: "telemetry_start",
      description: "开始记录 F1 25 的 UDP 遥测（默认端口 20777，可在设置里改）。后台跑，跑满时长或 telemetry_stop 停止。不跑车时别开。",
      parameters: { durationSec: { type: "number", description: "最长秒数，默认 900" } },
      async execute(args) {
        const r = await startCollect(args.durationSec);
        return r.ok ? `已开始采集（PID ${r.pid}，最长 ${r.durationSec}s，端口 ${r.udpPort}）` : r.error;
      },
    });

    register({
      name: "telemetry_stop",
      description: "停止 赛车遥测采集，已采数据保留。",
      parameters: {},
      async execute() {
        const r = stopCollect();
        return r.ok ? `已停止（PID ${r.pid}，跑了 ${r.seconds}s）` : r.error;
      },
    });

    register({
      name: "telemetry_summary",
      description: "分析已采集的 赛车遥测，只返回省 token 的结论：圈速、与最佳的差、最慢的弯、该改什么。",
      parameters: {},
      async execute() {
        const r = await runPython("summary.py", [], 180000);
        const out = r.stdout.split("\n").slice(0, 40).join("\n");
        return out || (r.stderr ? `失败：${r.stderr}` : "没有可分析的数据。");
      },
    });

    register({
      name: "telemetry_plot",
      description: "生成 赛车遥测速度曲线图与油门刹车图，返回 PNG 路径。",
      parameters: {},
      async execute() {
        const r = await runPython("plot.py", [], 240000);
        const lines = r.stdout.split("\n").filter((l) => l.includes(":") || l.includes("圈数"));
        return lines.slice(0, 8).join("\n") || r.stderr || "没有数据可画。";
      },
    });

    // ---- 设置面板用的 HTTP 路由 ----
    try {
      if (ctx.webServer && typeof ctx.webServer.register === "function") {
        ctx.effect(() => ctx.webServer.register({
          kind: "prefix",
          path: "/api/sim-telemetry",
          handler: async (req, res) => {
            const send = (code, obj) => {
              try { res.statusCode = code; res.setHeader("content-type", "application/json; charset=utf-8"); res.end(JSON.stringify(obj)); } catch { /* 连接已断 */ }
            };
            try {
              const url = new URL(req.url, "http://127.0.0.1");
              const path = url.pathname;
              const body = () => new Promise((resolve) => {
                let raw = "";
                req.on("data", (c) => { raw += c; });
                req.on("end", () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch { resolve({}); } });
                req.on("error", () => resolve({}));
              });
              if (req.method === "GET" && path === "/api/sim-telemetry/status") return send(200, status());
              if (req.method === "GET" && path === "/api/sim-telemetry/recheck") {
                probe = { running: false, done: false, info: null };
                startProbe();
                return send(200, status());
              }
              if (req.method === "POST" && path === "/api/sim-telemetry/settings") {
                const b = await body();
                if (typeof b.enabled === "boolean") cfg.enabled = b.enabled;
                if (Number(b.durationSec) > 0) cfg.durationSec = Math.max(30, Math.min(3600, Number(b.durationSec)));
                if (b.autoReportLaps !== undefined) cfg.autoReportLaps = Math.max(0, Math.min(50, Number(b.autoReportLaps) || 0));
                if (typeof b.pythonPath === "string") {
                  cfg.pythonPath = b.pythonPath.trim();
                  probe = { running: false, done: false, info: null };
                  startProbe();
                }
                if (b.udpPort !== undefined) {
                  const p = Number(b.udpPort);
                  if (p >= 1 && p <= 65535) cfg.udpPort = Math.floor(p);
                }

                writeSettings({
                  enabled: cfg.enabled, durationSec: cfg.durationSec, autoReportLaps: cfg.autoReportLaps,
                  pythonPath: cfg.pythonPath || "", udpPort: cfg.udpPort || 20777,
                });
                return send(200, status());
              }
              if (req.method === "POST" && path === "/api/sim-telemetry/install-python") return send(200, installPython());
              if (req.method === "POST" && path === "/api/sim-telemetry/install-deps") return send(200, installDeps());
              if (req.method === "POST" && path === "/api/sim-telemetry/start") {
                const b = await body();
                const r = await startCollect(b.durationSec);
                return send(200, { ...r, ...status() });
              }
              if (req.method === "POST" && path === "/api/sim-telemetry/stop") {
                const r = stopCollect();
                return send(200, { ...r, ...status() });
              }
              return send(404, { ok: false, error: `unknown ${req.method} ${path}` });
            } catch (err) {
              return send(500, { ok: false, error: String((err && err.message) || err) });
            }
          },
        }), "sim-telemetry: settings route");
        dbg("webServer 路由已注册");
      } else {
        dbg("ctx.webServer 不可用，跳过路由");
      }
    } catch (err) {
      dbg(`路由注册失败（已兜住）：${(err && err.message) || err}`);
    }

    dbg("apply 完成");
  } catch (err) {
    dbg(`apply 异常（已兜住）：${(err && (err.stack || err.message)) || err}`);
  }
}
