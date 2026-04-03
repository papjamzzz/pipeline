import json
import os
import subprocess
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

PIPELINE_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.json")


def load_pipeline():
    with open(PIPELINE_JSON, "r") as f:
        return json.load(f)


def save_pipeline(data):
    with open(PIPELINE_JSON, "w") as f:
        json.dump(data, f, indent=2)


def run_git(cmd, cwd):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip(), result.returncode
    except Exception:
        return None, -1


def get_git_data(path_raw):
    path = os.path.expanduser(path_raw)
    if not os.path.isdir(path):
        return {"error": "path not found"}

    git_check, rc = run_git(["git", "rev-parse", "--is-inside-work-tree"], path)
    if rc != 0 or git_check != "true":
        return {"error": "not a git repo"}

    log_out, _ = run_git(
        ["git", "log", "-1", "--pretty=format:%H|%ar|%s|%an"],
        path
    )
    branch_out, _ = run_git(["git", "branch", "--show-current"], path)
    status_out, _ = run_git(["git", "status", "--porcelain"], path)

    commit_hash = ""
    commit_time = ""
    commit_msg = ""
    commit_author = ""

    if log_out:
        parts = log_out.split("|", 3)
        if len(parts) == 4:
            commit_hash = parts[0][:7]
            commit_time = parts[1]
            commit_msg = parts[2]
            commit_author = parts[3]

    dirty = False
    changed_count = 0
    if status_out is not None:
        lines = [l for l in status_out.split("\n") if l.strip()]
        dirty = len(lines) > 0
        changed_count = len(lines)

    return {
        "hash": commit_hash,
        "time": commit_time,
        "message": commit_msg,
        "author": commit_author,
        "branch": branch_out or "unknown",
        "dirty": dirty,
        "changed_count": changed_count,
        "error": None
    }


def get_all_statuses(pipeline):
    results = []
    for project in pipeline["projects"]:
        git = get_git_data(project["path"])
        results.append({
            "id": project["id"],
            "name": project["name"],
            "github": project["github"],
            "port": project["port"],
            "status": project["status"],
            "url": project.get("url", ""),
            "path": project["path"],
            "accomplished": project.get("accomplished", []),
            "next": project.get("next", []),
            "git": git
        })
    # Sort: in-progress first, then live, then others
    order = {"in-progress": 0, "live": 1}
    results.sort(key=lambda x: order.get(x["status"], 99))
    return results


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CK DEV PIPELINE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0B1210;
  --bg-card: #0f1a17;
  --bg-card-hover: #131f1b;
  --border: #1e2e29;
  --green: #5EE88A;
  --amber: #F0A030;
  --gray: #666;
  --text: #c8d8d2;
  --text-dim: #7a9990;
  --text-bright: #e8f4f0;
  --font-mono: 'JetBrains Mono', monospace;
  --font-body: 'Inter', sans-serif;
  --font-head: 'Space Grotesk', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.5;
  min-height: 100vh;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #2a3d37; border-radius: 2px; }

/* HEADER */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg);
  z-index: 100;
}

.header-left h1 {
  font-family: var(--font-head);
  font-size: 22px;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 4px;
  text-transform: uppercase;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
}

.header-label {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-dim);
}

.clock {
  color: var(--text-bright);
  font-size: 12px;
  font-weight: 600;
}

.refresh-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
}

.refresh-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  opacity: 0.6;
  transition: opacity 0.2s;
}

.refresh-indicator.flashing .dot {
  opacity: 1;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
}

/* MAIN CONTENT */
.main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.section-label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--text-dim);
  text-transform: uppercase;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

/* GRID */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 28px;
}

@media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }

/* CARD */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
  border-radius: 4px;
  padding: 14px;
  transition: background 0.15s;
}

.card:hover { background: var(--bg-card-hover); }
.card.status-live { border-left-color: var(--green); }
.card.status-in-progress { border-left-color: var(--amber); }
.card.status-paused { border-left-color: var(--gray); }

.card-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-row:last-child { margin-bottom: 0; }

.project-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  color: var(--text-bright);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* STATUS LED */
.led {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.led.live {
  background: var(--green);
  box-shadow: 0 0 4px var(--green);
  animation: pulse 2.5s ease-in-out infinite;
}

.led.in-progress {
  background: var(--amber);
  box-shadow: 0 0 4px var(--amber);
}

.led.paused {
  background: var(--gray);
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px var(--green); }
  50% { opacity: 0.5; box-shadow: 0 0 2px var(--green); }
}

/* PORT BADGE */
.port-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--bg);
  background: var(--text-dim);
  padding: 1px 6px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* GITHUB */
.github-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* COMMIT ROW */
.commit-row {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
  display: flex;
  gap: 6px;
  align-items: baseline;
}

.commit-time {
  color: var(--green);
  white-space: nowrap;
  flex-shrink: 0;
}

.commit-hash {
  color: var(--text-dim);
  white-space: nowrap;
  flex-shrink: 0;
  opacity: 0.7;
}

.commit-msg {
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-git {
  color: var(--gray);
  font-style: italic;
}

/* BRANCH ROW */
.branch-row {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
  display: flex;
  align-items: center;
  gap: 6px;
}

.branch-name {
  color: var(--text);
}

.clean-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.clean-dot.clean { background: var(--green); }
.clean-dot.dirty { background: var(--amber); }

.dirty-label {
  font-size: 10px;
}

/* ROADMAP */
.roadmap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 700px) { .roadmap { grid-template-columns: 1fr; } }

.roadmap-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 14px;
}

.roadmap-panel.accomplished { border-top: 2px solid var(--green); }
.roadmap-panel.next { border-top: 2px solid var(--amber); }

.roadmap-title {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.roadmap-panel.accomplished .roadmap-title { color: var(--green); }
.roadmap-panel.next .roadmap-title { color: var(--amber); }

.roadmap-group {
  margin-bottom: 12px;
}

.roadmap-group:last-child { margin-bottom: 0; }

.roadmap-group-name {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-dim);
  margin-bottom: 4px;
  letter-spacing: 1px;
}

.roadmap-item {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text);
  padding: 2px 0 2px 12px;
  position: relative;
  line-height: 1.4;
}

.roadmap-item::before {
  content: '—';
  position: absolute;
  left: 0;
  color: var(--text-dim);
}

.roadmap-panel.accomplished .roadmap-item::before { color: var(--green); opacity: 0.5; }
.roadmap-panel.next .roadmap-item::before { color: var(--amber); opacity: 0.6; }

/* URL ROW */
.url-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.url-text {
  font-family: var(--font-mono);
  font-size: 10px;
  color: #ff4d4d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  text-decoration: none;
}

.url-text:hover { color: #ff7070; text-decoration: underline; }

.copy-btn {
  flex-shrink: 0;
  background: #1e0a0a;
  border: 1px solid #ff4d4d44;
  color: #ff4d4d;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 2px 7px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.copy-btn:hover {
  background: #ff4d4d22;
  border-color: #ff4d4d;
}

.copy-btn.copied {
  background: #0a1e0a;
  border-color: var(--green);
  color: var(--green);
}

/* TOAST */
#copy-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%) translateY(10px);
  background: #111;
  border: 1px solid var(--green);
  color: var(--green);
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 8px 18px;
  border-radius: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s, transform 0.2s;
  z-index: 999;
}

#copy-toast.show {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
</style>
</head>
<body>

<header class="header">
  <div class="header-left">
    <h1>PIPELINE</h1>
    <div class="header-label">CK DEV PIPELINE v1.0 — JEREMIAH / PAPJAMZZZ</div>
  </div>
  <div style="font-family:var(--font-mono);font-size:11px;color:var(--amber);letter-spacing:1px;border:1px solid var(--amber);padding:5px 14px;border-radius:4px;opacity:0.85;">
    /sync — Claude reads session · updates accomplished/next · pushes to GitHub
  </div>
  <div class="header-right">
    <div class="clock" id="clock">--:--:--</div>
    <div class="refresh-indicator" id="refresh-indicator">
      <div class="dot"></div>
      <span id="refresh-countdown">AUTO-REFRESH IN 30s</span>
    </div>
  </div>
</header>

<main class="main">
  <div class="section-label">PROJECTS — {{ projects | length }} ACTIVE</div>
  <div class="grid" id="project-grid">
    {% for p in projects %}
    <div class="card status-{{ p.status }}" data-id="{{ p.id }}">
      <!-- Row 1: Name + LED + Port -->
      <div class="card-row">
        <span class="project-name">{{ p.name }}</span>
        <div class="led {{ p.status }}" title="{{ p.status }}"></div>
        {% if p.port and p.port > 0 %}
        <span class="port-badge">:{{ p.port }}</span>
        {% endif %}
      </div>
      <!-- Row 2: GitHub + URL -->
      <div class="card-row">
        <span class="github-text">github / {{ p.github }}</span>
      </div>
      {% if p.url %}
      <div class="card-row">
        <div class="url-row">
          <a class="url-text" href="{{ p.url }}" target="_blank" title="{{ p.url }}">{{ p.url }}</a>
          <button class="copy-btn" onclick="copyUrl(this, '{{ p.url }}')">CC</button>
        </div>
      </div>
      {% endif %}
      <!-- Row 3: Last commit -->
      <div class="card-row">
        {% if p.git.error %}
        <span class="no-git">{{ p.git.error }}</span>
        {% else %}
        <div class="commit-row">
          <span class="commit-time">{{ p.git.time }}</span>
          <span class="commit-hash">{{ p.git.hash }}</span>
          <span class="commit-msg">{{ p.git.message[:60] }}{% if p.git.message|length > 60 %}…{% endif %}</span>
        </div>
        {% endif %}
      </div>
      <!-- Row 4: Branch + clean/dirty -->
      <div class="card-row">
        {% if not p.git.error %}
        <div class="branch-row">
          <span style="color:var(--text-dim)">branch:</span>
          <span class="branch-name">{{ p.git.branch }}</span>
          <div class="clean-dot {% if p.git.dirty %}dirty{% else %}clean{% endif %}"></div>
          {% if p.git.dirty %}
          <span class="dirty-label" style="color:var(--amber)">{{ p.git.changed_count }} changed</span>
          {% else %}
          <span class="dirty-label" style="color:var(--green)">clean</span>
          {% endif %}
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- ROADMAP SECTION -->
  <div class="section-label" style="margin-top:8px;">ROADMAP</div>
  <div class="roadmap">
    <!-- ACCOMPLISHED -->
    <div class="roadmap-panel accomplished">
      <div class="roadmap-title">ACCOMPLISHED</div>
      {% for p in projects %}
      {% if p.accomplished %}
      <div class="roadmap-group">
        <div class="roadmap-group-name">{{ p.name }}</div>
        {% for item in p.accomplished %}
        <div class="roadmap-item">{{ item }}</div>
        {% endfor %}
      </div>
      {% endif %}
      {% endfor %}
    </div>
    <!-- NEXT UP -->
    <div class="roadmap-panel next">
      <div class="roadmap-title">NEXT UP</div>
      {% for p in projects %}
      {% if p.next %}
      <div class="roadmap-group">
        <div class="roadmap-group-name">{{ p.name }}</div>
        {% for item in p.next %}
        <div class="roadmap-item">{{ item }}</div>
        {% endfor %}
      </div>
      {% endif %}
      {% endfor %}
    </div>
  </div>
</main>

<div id="copy-toast">COPIED</div>

<script>
// Copy URL
function copyUrl(btn, url) {
  navigator.clipboard.writeText(url).then(() => {
    btn.textContent = '✓';
    btn.classList.add('copied');
    const toast = document.getElementById('copy-toast');
    toast.classList.add('show');
    setTimeout(() => {
      btn.textContent = 'CC';
      btn.classList.remove('copied');
      toast.classList.remove('show');
    }, 1800);
  });
}

// Clock
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  document.getElementById('clock').textContent = h + ':' + m + ':' + s;
}
setInterval(updateClock, 1000);
updateClock();

// Auto-refresh
let countdown = 30;
const countdownEl = document.getElementById('refresh-countdown');
const indicatorEl = document.getElementById('refresh-indicator');

function updateCountdown() {
  countdown--;
  if (countdown <= 0) {
    countdown = 30;
    doRefresh();
  }
  countdownEl.textContent = 'AUTO-REFRESH IN ' + countdown + 's';
}

function doRefresh() {
  indicatorEl.classList.add('flashing');
  fetch('/api/status')
    .then(r => r.json())
    .then(data => {
      updateCards(data);
      setTimeout(() => indicatorEl.classList.remove('flashing'), 600);
    })
    .catch(() => indicatorEl.classList.remove('flashing'));
}

function updateCards(projects) {
  projects.forEach(p => {
    const card = document.querySelector('.card[data-id="' + p.id + '"]');
    if (!card) return;

    // Update commit row (row index 2)
    const rows = card.querySelectorAll('.card-row');
    if (rows.length >= 3) {
      const commitRow = rows[2];
      const git = p.git;
      if (git.error) {
        commitRow.innerHTML = '<span class="no-git">' + git.error + '</span>';
      } else {
        const msg = git.message.length > 60 ? git.message.substring(0, 60) + '…' : git.message;
        commitRow.innerHTML = '<div class="commit-row"><span class="commit-time">' + git.time + '</span><span class="commit-hash">' + git.hash + '</span><span class="commit-msg">' + msg + '</span></div>';
      }
    }
    if (rows.length >= 4) {
      const branchRow = rows[3];
      const git = p.git;
      if (!git.error) {
        const dotClass = git.dirty ? 'dirty' : 'clean';
        const label = git.dirty
          ? '<span class="dirty-label" style="color:var(--amber)">' + git.changed_count + ' changed</span>'
          : '<span class="dirty-label" style="color:var(--green)">clean</span>';
        branchRow.innerHTML = '<div class="branch-row"><span style="color:var(--text-dim)">branch:</span><span class="branch-name">' + git.branch + '</span><div class="clean-dot ' + dotClass + '"></div>' + label + '</div>';
      }
    }
  });
}

setInterval(updateCountdown, 1000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    pipeline = load_pipeline()
    projects = get_all_statuses(pipeline)
    return render_template_string(TEMPLATE, projects=projects)


@app.route("/api/status")
def api_status():
    pipeline = load_pipeline()
    projects = get_all_statuses(pipeline)
    return jsonify(projects)


@app.route("/api/update/<project_id>", methods=["POST"])
def api_update(project_id):
    pipeline = load_pipeline()
    body = request.get_json(force=True)
    updated = False
    for project in pipeline["projects"]:
        if project["id"] == project_id:
            if "accomplished" in body:
                project["accomplished"] = body["accomplished"]
            if "next" in body:
                project["next"] = body["next"]
            updated = True
            break
    if not updated:
        return jsonify({"error": "project not found"}), 404
    save_pipeline(pipeline)
    return jsonify({"ok": True, "id": project_id})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5561, debug=False)
