const cwd = process.env.CF_MAIN_REPO || "/home/claude/contentflow/contentflow_lab";

module.exports = {
  apps: [{
    name: "contentflow_lab",
    cwd,
    script: "bash",
    args: ["-lc", `cd "${cwd}" && export PORT=3000 && flox activate -- doppler run --project winflowz --config prd -- bash -lc './run_seo_tools.sh ./.venv/bin/python3 main.py'`],
    env: {
      PORT: 3000
    },
    autorestart: true,
    watch: false
  }]
};
