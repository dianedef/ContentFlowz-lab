module.exports = {
  apps: [{
    name: "contentflow_lab",
    cwd: "/home/claude/contentflow_lab",
    script: "bash",
    args: ["-lc", "export PORT=3000 && flox activate -- bash -lc './run_seo_tools.sh ./.venv/bin/python main.py'"],
    env: {
      PORT: 3000
    },
    autorestart: true,
    watch: false
  }]
};
