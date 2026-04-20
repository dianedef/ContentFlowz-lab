const fs = require('fs');
const path = require('path');

const cwd =
  process.env.CF_MAIN_REPO ||
  (fs.existsSync('/home/claude/ContentFlow/contentflow_lab')
    ? '/home/claude/ContentFlow/contentflow_lab'
    : fs.existsSync('/home/claude/contentflow_lab')
      ? '/home/claude/contentflow_lab'
      : path.resolve(__dirname));

module.exports = {
  apps: [{
    name: "contentflow_lab",
    cwd,
    script: "bash",
    args: ["-lc", "export PORT=3000 && flox activate -- doppler run -- bash -lc './run_seo_tools.sh ./.venv/bin/python main.py'"],
    env: {
      PORT: 3000
    },
    autorestart: true,
    watch: false
  }]
};
