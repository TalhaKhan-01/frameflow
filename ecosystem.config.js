// Frameflow's long-running processes, for the personal PM2 (PM2_HOME=~/.pm2-personal).
const ROOT = "/home/talha-khan/Talha_Khan/Code/frameflow";
const PD = `${ROOT}/phasedoc`;

module.exports = {
  apps: [
    {
      name: "phasedoc-frameflow",
      cwd: ROOT,
      script: "/usr/bin/python3",
      interpreter: "none",
      args: ["/home/talha-khan/Talha_Khan/Code/phasedoc-cockpit/cockpit.py"],
      env: {
        PD_PORT: "7300",
        PD_HOST: "127.0.0.1",
        PD_DB: `${PD}/plan.db`,
        PD_TITLE: "Frameflow",
        PD_SUBTITLE: "Automated Shorts for YouTube and Instagram: build arc P0–P8",
        PD_PLAN: `${PD}/PLAN.md`,
        PD_ARCH: `${PD}/ARCHITECTURE.md`,
        PD_EXPLAINERS: `${PD}/explainers.json`,
        PD_RESOURCES: `${PD}/resources.json`,
        PD_LOG: `${ROOT}/vault/log.md`,
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      out_file: `${ROOT}/logs/cockpit.out.log`,
      error_file: `${ROOT}/logs/cockpit.err.log`,
    },
    {
      // The Pilot's own Chrome: only the Thirdspace logins (YouTube Studio, Instagram), DevTools on 127.0.0.1:7307.
      // Talha's main Chrome (personal + office profiles) never needs remote debugging.
      name: "frameflow-chrome",
      cwd: ROOT,
      script: "/usr/bin/google-chrome",
      interpreter: "none",
      args: ["--user-data-dir=/home/talha-khan/.cache/frameflow/pilot-chrome", "--remote-debugging-port=7307",
             "--remote-debugging-address=127.0.0.1", "--no-first-run", "--no-default-browser-check",
             "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
             "https://studio.youtube.com"],
      env: { DISPLAY: ":1", XAUTHORITY: "/run/user/1000/gdm/Xauthority", DBUS_SESSION_BUS_ADDRESS: "unix:path=/run/user/1000/bus" },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 10000,
      out_file: `${ROOT}/logs/chrome.out.log`,
      error_file: `${ROOT}/logs/chrome.err.log`,
    },
    {
      // Telegram bot + the daily tick (20:00 topic card, 22:30 auto-pick, 11:30 posting).
      name: "frameflow-bot",
      cwd: ROOT,
      script: "/home/talha-khan/.local/bin/uv",
      interpreter: "none",
      args: ["run", "python", "-m", "frameflow.bot"],
      env: { PYTHONUNBUFFERED: "1", DISPLAY: ":1", XAUTHORITY: "/run/user/1000/gdm/Xauthority" },
      autorestart: true,
      max_restarts: 50,
      restart_delay: 10000,
      out_file: `${ROOT}/logs/bot.out.log`,
      error_file: `${ROOT}/logs/bot.err.log`,
    },
  ],
};
