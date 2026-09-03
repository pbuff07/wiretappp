const { app, BrowserWindow, shell, nativeImage } = require("electron");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { execSync, spawn } = require("child_process");

const isPackaged = app.isPackaged;
const DEV_ROOT = path.resolve(__dirname, "..");
const RESOURCES = isPackaged ? path.join(process.resourcesPath, "wiretappp") : DEV_ROOT;
const ROOT = isPackaged ? RESOURCES : DEV_ROOT;
const FRONTEND_DIR = path.join(DEV_ROOT, "frontend");
const FRONTEND_DIST = isPackaged
  ? path.join(process.resourcesPath, "frontend", "dist")
  : path.join(FRONTEND_DIR, "dist");
const VITE_PORT = 5173;
const VITE_URL = `http://127.0.0.1:${VITE_PORT}`;

let mainWindow = null;
let backendProc = null;
let viteProc = null;
let startedBackend = false;
let startedVite = false;

function wiretapppHome() {
  if (process.env.WIRETAPPP_HOME) {
    return path.resolve(process.env.WIRETAPPP_HOME);
  }
  if (process.platform === "win32") {
    const appdata = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
    return path.join(appdata, "wiretappp");
  }
  if (process.platform === "linux") {
    const xdg = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config");
    return path.join(xdg, "wiretappp");
  }
  return path.join(os.homedir(), ".wiretappp");
}

function ensureUserLayout() {
  const home = wiretapppHome();
  const logDir = isPackaged ? path.join(home, "logs") : path.join(DEV_ROOT, "logs");
  const runDir = isPackaged ? path.join(home, "run") : path.join(DEV_ROOT, "run");
  for (const dir of [
    home,
    path.join(home, "data"),
    path.join(home, "data", "mitmproxy"),
    logDir,
    runDir,
  ]) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const cfgPath = path.join(home, "config.yaml");
  if (!fs.existsSync(cfgPath)) {
    const defaults = [
      path.join(RESOURCES, "config.yaml.default"),
      path.join(DEV_ROOT, "config.yaml"),
    ];
    const seed = defaults.find((candidate) => fs.existsSync(candidate));
    if (seed) {
      fs.copyFileSync(seed, cfgPath);
    } else {
      fs.writeFileSync(
        cfgPath,
        [
          "listen_host: 127.0.0.1",
          "listen_port: 8080",
          "api_host: 127.0.0.1",
          "api_port: 18760",
          "static_suffixes: [.js, .css, .png, .jpg, .svg, .woff2]",
          "max_body_bytes: 524288",
          "",
        ].join("\n"),
        "utf8",
      );
    }
  }
  return home;
}

function readConfig() {
  const defaults = { api_host: "127.0.0.1", api_port: 18760 };
  const cfgPath = path.join(wiretapppHome(), "config.yaml");
  if (!fs.existsSync(cfgPath)) return defaults;
  const text = fs.readFileSync(cfgPath, "utf8");
  const pick = (key) => {
    const match = text.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
    return match ? match[1].trim().replace(/^["']|["']$/g, "") : undefined;
  };
  return {
    api_host: pick("api_host") || defaults.api_host,
    api_port: Number(pick("api_port") || defaults.api_port),
  };
}

function pythonBin() {
  const candidates =
    process.platform === "win32"
      ? [
          path.join(RESOURCES, "python-env", "Scripts", "python.exe"),
          path.join(DEV_ROOT, ".venv", "Scripts", "python.exe"),
        ]
      : [
          path.join(RESOURCES, "python-env", "bin", "python3"),
          path.join(RESOURCES, "python-env", "bin", "python"),
          path.join(DEV_ROOT, ".venv", "bin", "python3"),
          path.join(DEV_ROOT, ".venv", "bin", "python"),
        ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function uvicornBin() {
  const candidates =
    process.platform === "win32"
      ? [
          path.join(RESOURCES, "python-env", "Scripts", "uvicorn.exe"),
          path.join(DEV_ROOT, ".venv", "Scripts", "uvicorn.exe"),
        ]
      : [
          path.join(RESOURCES, "python-env", "bin", "uvicorn"),
          path.join(DEV_ROOT, ".venv", "bin", "uvicorn"),
        ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function npmBin() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function runtimeEnv(home) {
  const logDir = isPackaged ? path.join(home, "logs") : path.join(DEV_ROOT, "logs");
  const runDir = isPackaged ? path.join(home, "run") : path.join(DEV_ROOT, "run");
  return {
    ...process.env,
    WIRETAPPP_HOME: home,
    WIRETAPPP_PACKAGED: isPackaged ? "1" : "0",
    PYTHONPATH: ROOT + path.delimiter + (process.env.PYTHONPATH || ""),
    WIRETAPPP_LOG_DIR: logDir,
    WIRETAPPP_RUN_DIR: runDir,
  };
}

function localApiUrl(port) {
  return `http://127.0.0.1:${port}`;
}

function waitForHttp(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) resolve(true);
        else if (Date.now() >= deadline) reject(new Error(`unexpected status ${res.statusCode}`));
        else setTimeout(attempt, 200);
      });
      req.on("error", () => {
        if (Date.now() >= deadline) reject(new Error(`${url} did not become ready`));
        else setTimeout(attempt, 200);
      });
      req.setTimeout(1500, () => req.destroy());
    };
    attempt();
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function fetchJson(url, timeoutMs = 3000) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });
      res.on("end", () => {
        if (res.statusCode && res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      reject(new Error("timeout"));
    });
  });
}

async function backendHasRecon(port) {
  try {
    const spec = await fetchJson(`${localApiUrl(port)}/openapi.json`, 3000);
    return Boolean(spec.paths && spec.paths["/api/recon"]);
  } catch {
    return false;
  }
}

function killPortListeners(port) {
  if (process.platform === "win32") return;
  try {
    const out = execSync(`lsof -ti :${port}`, { encoding: "utf8" }).trim();
    if (!out) return;
    for (const pid of out.split("\n")) {
      if (!pid) continue;
      try {
        process.kill(Number(pid), "SIGTERM");
      } catch {
        // ignore
      }
    }
  } catch {
    // no listeners
  }
}

async function ensureBackend(home) {
  const cfg = readConfig();
  const port = cfg.api_port;
  let running = false;
  try {
    await waitForHttp(`${localApiUrl(port)}/api/health`, 1200);
    running = true;
  } catch {
    running = false;
  }

  if (running && (await backendHasRecon(port))) {
    return port;
  }

  if (running) {
    console.error(`[wiretappp] API on :${port} is stale (missing Recon routes), restarting...`);
    killPortListeners(port);
    await sleep(600);
  }

  const python = pythonBin();
  const uvicorn = uvicornBin();
  if (!python || !uvicorn) {
    const hint = isPackaged
      ? "应用内置 Python 环境缺失，请重新安装 WIRETAPPP"
      : "Python 虚拟环境未就绪，请先在项目根目录执行 ./manage.sh install";
    throw new Error(hint);
  }

  const logDir = isPackaged ? path.join(home, "logs") : path.join(DEV_ROOT, "logs");
  const runDir = isPackaged ? path.join(home, "run") : path.join(DEV_ROOT, "run");
  fs.mkdirSync(logDir, { recursive: true });
  fs.mkdirSync(runDir, { recursive: true });
  const logPath = path.join(logDir, "api.log");
  const logStream = fs.createWriteStream(logPath, { flags: "a" });

  backendProc = spawn(
    uvicorn,
    ["backend.main:app", "--host", cfg.api_host, "--port", String(port), "--log-level", "info"],
    {
      cwd: ROOT,
      env: runtimeEnv(home),
      stdio: ["ignore", "pipe", "pipe"],
      detached: process.platform !== "win32",
    },
  );
  startedBackend = true;
  backendProc.stdout.pipe(logStream, { end: false });
  backendProc.stderr.pipe(logStream, { end: false });

  backendProc.on("exit", (code, signal) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const reason = signal ? `signal ${signal}` : `code ${code}`;
      mainWindow.webContents.send("wiretappp-backend-exit", reason);
    }
    backendProc = null;
    startedBackend = false;
  });

  await waitForHttp(`${localApiUrl(port)}/api/health`);
  if (!(await backendHasRecon(port))) {
    throw new Error("API started but /api/recon is missing; check logs/api.log");
  }
  return port;
}

async function ensureVite() {
  if (isPackaged) return;

  try {
    await waitForHttp(VITE_URL, 1200);
    return;
  } catch {
    // not running, start below
  }

  if (!fs.existsSync(path.join(FRONTEND_DIR, "node_modules", "vite"))) {
    throw new Error("前端依赖未安装，请先在项目根目录执行 ./manage.sh install");
  }

  const logPath = path.join(DEV_ROOT, "logs", "vite.log");
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logStream = fs.createWriteStream(logPath, { flags: "a" });

  viteProc = spawn(
    npmBin(),
    ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(VITE_PORT), "--strictPort"],
    {
      cwd: FRONTEND_DIR,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      shell: process.platform === "win32",
      detached: process.platform !== "win32",
    },
  );
  startedVite = true;
  viteProc.stdout.pipe(logStream, { end: false });
  viteProc.stderr.pipe(logStream, { end: false });

  viteProc.on("exit", (code, signal) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const reason = signal ? `signal ${signal}` : `code ${code}`;
      mainWindow.webContents.send("wiretappp-vite-exit", reason);
    }
    viteProc = null;
    startedVite = false;
  });

  await waitForHttp(VITE_URL);
}

function stopChild(proc, started) {
  if (!proc || !started) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(proc.pid), "/f", "/t"]);
    return;
  }
  try {
    process.kill(-proc.pid, "SIGTERM");
  } catch {
    try {
      proc.kill("SIGTERM");
    } catch {
      // ignore
    }
  }
}

function stopBackend() {
  if (!backendProc || !startedBackend) return;
  stopChild(backendProc, startedBackend);
  backendProc = null;
  startedBackend = false;
}

function stopVite() {
  if (!viteProc || !startedVite) return;
  stopChild(viteProc, startedVite);
  viteProc = null;
  startedVite = false;
}

function appIconPath() {
  const logo = path.join(__dirname, "assets", "logo.png");
  if (fs.existsSync(logo)) return logo;
  const built = path.join(__dirname, "build", process.platform === "win32" ? "icon.ico" : "icon.png");
  if (fs.existsSync(built)) return built;
  return undefined;
}

function applyAppIcon() {
  const iconFile = appIconPath();
  if (!iconFile) return undefined;
  const icon = nativeImage.createFromPath(iconFile);
  if (icon.isEmpty()) return undefined;
  if (process.platform === "darwin" && app.dock) {
    app.dock.setIcon(icon);
  }
  return icon;
}

function createWindow(loadUrl) {
  const icon = applyAppIcon();
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 980,
    minHeight: 640,
    title: "WIRETAPPP",
    icon: icon || undefined,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  if (loadUrl.startsWith("http")) {
    mainWindow.loadURL(loadUrl);
  } else {
    mainWindow.loadFile(loadUrl);
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  try {
    const home = ensureUserLayout();
    await ensureBackend(home);
    if (isPackaged) {
      const indexHtml = path.join(FRONTEND_DIST, "index.html");
      if (!fs.existsSync(indexHtml)) {
        throw new Error(`前端资源缺失: ${indexHtml}`);
      }
      createWindow(indexHtml);
    } else {
      await ensureVite();
      createWindow(VITE_URL);
    }
  } catch (err) {
    console.error(err);
    app.exit(1);
  }
});

app.on("window-all-closed", () => {
  stopVite();
  stopBackend();
  app.quit();
});

app.on("before-quit", () => {
  stopVite();
  stopBackend();
});

app.on("activate", async () => {
  if (mainWindow) return;
  try {
    const home = ensureUserLayout();
    await ensureBackend(home);
    if (isPackaged) {
      createWindow(path.join(FRONTEND_DIST, "index.html"));
    } else {
      await ensureVite();
      createWindow(VITE_URL);
    }
  } catch (err) {
    console.error(err);
  }
});
