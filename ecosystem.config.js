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
  ],
};
