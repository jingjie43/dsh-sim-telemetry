/**
 * dsh-f1-telemetry —— F1 25 UDP 遥测采集/分析插件（v3：安全加载版）
 *
 * 原则：加载阶段绝不抛错。所有异常写进 <data>/debug.log，最多次功能缺失，不会把宿主带崩。
 * 工具：f1_start / f1_stop / f1_summary / f1_plot
 */
import { spawn, execFile, spawnSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import { defineTool } from "@deepseek-ai/dsh-tools";

export const name = "f1-telemetry";
export const inject = ["tools", "webServer"];

const PY_DIR = fileURLToPath(new URL("./lib/py/", import.meta.url));
const DEFAULT_PY = "C:\\Users\\Lenovo\\AppData\\Local\\Programs\\Python\\Python312\\python.exe";
const DEFAULTS = { enabled: true, durationSec: 900, autoReportLaps: 0, pythonPath: "" };
const state = { proc: null, startedAt: 0 };
let cfg = { ...DEFAULTS };

function dataDir() {
  const home = process.env.DSH_HOME || join(homedir(), ".dsh");
  const dir = join(home, "f1-telemetry");
  try { mkdirSync(dir, { recursive: true }); } catch { /* 忽略 */ }
  return dir;
}

function dbg(msg) {
  try { appendFileSync(join(dataDir(), "debug.log"), `${new Date().toISOString()} ${msg}\n`); } catch { /* 忽略 */ }
}

let cachedPython = null;

function pythonExe() {
  if (cachedPython) return cachedPython;
  const candidates = [];
  if (cfg.pythonPath) candidates.push(cfg.pythonPath);
  if (process.env.F1_PYTHON) candidates.push(process.env.F1_PYTHON);
  if (existsSync(DEFAULT_PY)) candidates.push(DEFAULT_PY);
  candidates.push("python", "python3", "py");
  for (const candidate of candidates) {
    try {
      const r = spawnSync(candidate, ["-c", "import sys;print(sys.version_info[0])"], {
        timeout: 5000, windowsHide: true, encoding: "utf8",
      });
      if (r && r.status === 0 && String(r.stdout || "").trim() === "3") {
        cachedPython = candidate;
        return candidate;
      }
    } catch { /* 试下一个 */ }
  }
  cachedPython = "python";
  return cachedPython;
}

function readSettings() {
  try { return JSON.parse(readFileSync(join(dataDir(), "settings.json"), "utf8")); } catch { return {}; }
}

function writeSettings(next) {
  try { writeFileSync(join(dataDir(), "settings.json"), JSON.stringify(next, null, 2), "utf8"); } catch { /* 忽略 */ }
}

function runPython(script, args = [], timeoutMs = 180000) {
  return new Promise((resolve) => {
    try {
      execFile(pythonExe(), [join(PY_DIR, script), ...args], {
        env: { ...process.env, F1_DATA_DIR: dataDir(), PYTHONIOENCODING: "utf-8" },
        timeout: timeoutMs,
        maxBuffer: 8 * 1024 * 1024,
        windowsHide: true,
      }, (error, stdout, stderr) => {
        resolve({
          ok: !error,
          stdout: String(stdout || "").trim(),
          stderr: String(stderr || "").trim().slice(-1200),
        });
      });
    } catch (err) {
      resolve({ ok: false, stdout: "", stderr: String((err && err.message) || err) });
    }
  });
}

function startCollect(durationSec) {
  if (state.proc) return { ok: false, error: "已经在采集中" };
  if (cfg.enabled === false) return { ok: false, error: "插件功能已关闭（设置页里打开开关）" };
  try {
    const dur = Math.max(30, Math.min(3600, Number(durationSec) || cfg.durationSec || 900));
    const child = spawn(pythonExe(), [join(PY_DIR, "f1_collect_all.py"), String(dur), String(cfg.autoReportLaps || 0)], {
      env: { ...process.env, F1_DATA_DIR: dataDir(), PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    state.proc = child;
    state.startedAt = Date.now();
    child.stdout.on("data", () => {});
    child.stderr.on("data", () => {});
    child.on("exit", () => { state.proc = null; });
    return { ok: true, pid: child.pid, durationSec: dur };
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
  return {
    ok: true,
    enabled: cfg.enabled !== false,
    durationSec: cfg.durationSec || 900,
    autoReportLaps: cfg.autoReportLaps || 0,
    collecting: Boolean(state.proc),
    dataDir: dataDir(),
    python: pythonExe(),
    pythonPath: cfg.pythonPath || "",
  };
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
      name: "f1_start",
      description: "开始记录 F1 25 的 UDP 遥测（端口 20777）。后台跑，跑满时长或 f1_stop 停止。不跑车时别开。",
      parameters: { durationSec: { type: "number", description: "最长秒数，默认 900" } },
      async execute(args) {
        const r = startCollect(args.durationSec);
        return r.ok ? `已开始采集（PID ${r.pid}，最长 ${r.durationSec}s）` : r.error;
      },
    });

    register({
      name: "f1_stop",
      description: "停止 F1 遥测采集，已采数据保留。",
      parameters: {},
      async execute() {
        const r = stopCollect();
        return r.ok ? `已停止（PID ${r.pid}，跑了 ${r.seconds}s）` : r.error;
      },
    });

    register({
      name: "f1_summary",
      description: "分析已采集的 F1 遥测，只返回省 token 的结论：圈速、与最佳的差、最慢的弯、该改什么。",
      parameters: {},
      async execute() {
        const r = await runPython("f1_summary.py", [], 180000);
        const out = r.stdout.split("\n").slice(0, 40).join("\n");
        return out || (r.stderr ? `失败：${r.stderr}` : "没有可分析的数据。");
      },
    });

    register({
      name: "f1_plot",
      description: "生成 F1 遥测速度曲线图与油门刹车图，返回 PNG 路径。",
      parameters: {},
      async execute() {
        const r = await runPython("f1_plot.py", [], 240000);
        const lines = r.stdout.split("\n").filter((l) => l.includes(":") || l.includes("圈数"));
        return lines.slice(0, 8).join("\n") || r.stderr || "没有数据可画。";
      },
    });

    // ---- 设置面板用的 HTTP 路由 ----
    try {
      if (ctx.webServer && typeof ctx.webServer.register === "function") {
        ctx.effect(() => ctx.webServer.register({
          kind: "prefix",
          path: "/api/f1-telemetry",
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
              if (req.method === "GET" && path === "/api/f1-telemetry/status") return send(200, status());
              if (req.method === "POST" && path === "/api/f1-telemetry/settings") {
                const b = await body();
                if (typeof b.enabled === "boolean") cfg.enabled = b.enabled;
                if (Number(b.durationSec) > 0) cfg.durationSec = Math.max(30, Math.min(3600, Number(b.durationSec)));
                if (b.autoReportLaps !== undefined) cfg.autoReportLaps = Math.max(0, Math.min(50, Number(b.autoReportLaps) || 0));
                if (typeof b.pythonPath === "string") { cfg.pythonPath = b.pythonPath.trim(); cachedPython = null; }

                writeSettings({ enabled: cfg.enabled, durationSec: cfg.durationSec, autoReportLaps: cfg.autoReportLaps, pythonPath: cfg.pythonPath || "" });
                return send(200, status());
              }
              if (req.method === "POST" && path === "/api/f1-telemetry/start") {
                const b = await body();
                const r = startCollect(b.durationSec);
                return send(200, { ...r, ...status() });
              }
              if (req.method === "POST" && path === "/api/f1-telemetry/stop") {
                const r = stopCollect();
                return send(200, { ...r, ...status() });
              }
              return send(404, { ok: false, error: `unknown ${req.method} ${path}` });
            } catch (err) {
              return send(500, { ok: false, error: String((err && err.message) || err) });
            }
          },
        }), "f1-telemetry: settings route");
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
