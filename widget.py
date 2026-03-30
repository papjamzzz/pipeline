#!/usr/bin/env python3
"""
CK Pipeline Widget — terminal dashboard, refreshes every 30s
Run in a dedicated Terminal window pinned to top-right.
"""
import json, os, subprocess, sys, time
from pathlib import Path

# ── ANSI ────────────────────────────────────────────────
R   = '\033[0m'
B   = '\033[1m'
DIM = '\033[2m'
G   = '\033[38;5;84m'    # green  #5EE88A-ish
A   = '\033[38;5;214m'   # amber
RD  = '\033[38;5;203m'   # red
WH  = '\033[38;5;252m'   # off-white
GR  = '\033[38;5;240m'   # gray dim
CY  = '\033[38;5;44m'    # cyan (branch)
HOME_CLEAR = '\033[2J\033[H'

W = 62  # widget width

PIPELINE_JSON = Path(__file__).parent / 'pipeline.json'

STATUS_COLOR = {
    'live':        G,
    'in-progress': A,
    'paused':      GR,
    'idea':        GR,
}
STATUS_GLYPH = {
    'live':        '●',
    'in-progress': '◐',
    'paused':      '○',
    'idea':        '◌',
}

# ── GIT ─────────────────────────────────────────────────
def git(path, cmd):
    try:
        r = subprocess.run(
            ['git'] + cmd, cwd=str(path),
            capture_output=True, text=True, timeout=4
        )
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:
        return ''

def project_git(raw_path):
    path = Path(os.path.expanduser(raw_path))
    if not path.exists():
        return {'hash': '—', 'time': '—', 'msg': 'path not found', 'branch': '—', 'dirty': False}

    log = git(path, ['log', '-1', '--pretty=format:%h|%ar|%s'])
    parts = log.split('|', 2) if log else []
    h   = parts[0] if len(parts) > 0 else '—'
    t   = parts[1] if len(parts) > 1 else '—'
    msg = parts[2] if len(parts) > 2 else '—'

    branch  = git(path, ['branch', '--show-current']) or 'main'
    dirty_r = git(path, ['status', '--porcelain'])
    dirty   = len([l for l in dirty_r.splitlines() if l.strip()]) if dirty_r else 0

    return {'hash': h, 'time': t, 'msg': msg[:38], 'branch': branch, 'dirty': dirty}

# ── DRAW ────────────────────────────────────────────────
def line(s=''):
    print(s)

def rule(char='─', color=GR):
    print(f'{color}' + char * W + R)

def header(now_str, countdown):
    rule('━', G)
    left  = f'{B}{G}CK PIPELINE{R}'
    right = f'{GR}refresh in {A}{countdown:02d}s{R}'
    # raw lengths for padding
    raw_left  = 'CK PIPELINE'
    raw_right = f'refresh in {countdown:02d}s'
    pad = W - len(raw_left) - len(raw_right)
    print(f'{left}{" " * pad}{right}')
    print(f'{GR}{now_str.center(W)}{R}')
    rule('━', G)

def card(proj, gd):
    sc = STATUS_COLOR.get(proj['status'], GR)
    sg = STATUS_GLYPH.get(proj['status'], '○')
    name = proj['name']
    port = f':{proj["port"]}' if proj.get('port', 0) > 0 else '   '
    gh   = proj.get('github', '')

    # Row 1: status glyph + name + port
    port_str = f'{DIM}{port}{R}'
    name_str = f'{B}{WH}{name}{R}'
    right_str = f'{sc}{sg}{R} {sc}{proj["status"]}{R}'
    raw1 = f'{sg} {name}{port}  {proj["status"]}'
    pad1 = W - len(raw1)
    print(f'{sc}{sg}{R} {name_str}{DIM}{port}{R}{"  " + " " * max(0, pad1)}{right_str}')

    # Row 2: github
    print(f'  {GR}{gh}{R}')

    # Row 3: last commit
    t_str  = f'{A}{gd["time"]}{R}'
    h_str  = f'{DIM}{gd["hash"]}{R}'
    m_str  = f'{GR}{gd["msg"]}{R}'
    print(f'  {t_str} {h_str} {m_str}')

    # Row 4: branch + dirty
    dirty_s = f'{A}  {gd["dirty"]} change{"s" if gd["dirty"] != 1 else ""}{R}' if gd['dirty'] else f'{G}  clean{R}'
    print(f'  {CY}branch:{gd["branch"]}{R}{dirty_s}')

def roadmap_section(projects):
    rule('─', GR)
    # NEXT UP — top 8 items across all projects
    next_items = []
    for p in projects:
        for item in p.get('next', []):
            next_items.append((p['name'], item))
    if not next_items:
        return
    print(f'{B}{A}▸ NEXT UP{R}')
    for name, item in next_items[:8]:
        label = f'{GR}[{name}]{R}'
        text  = f'{WH}{item}{R}'
        # truncate item to fit
        max_item = W - len(name) - 5
        display = item[:max_item] + ('…' if len(item) > max_item else '')
        print(f'  {GR}[{A}{name}{GR}]{R} {WH}{display}{R}')

# ── MAIN LOOP ────────────────────────────────────────────
def run():
    INTERVAL = 30

    while True:
        # load config fresh each cycle
        try:
            data = json.loads(PIPELINE_JSON.read_text())
            projects = data.get('projects', [])
        except Exception as e:
            projects = []

        # sort: in-progress first, then live, then rest
        order = {'in-progress': 0, 'live': 1}
        projects.sort(key=lambda p: order.get(p.get('status', ''), 2))

        # collect git data
        git_data = {}
        for p in projects:
            git_data[p['id']] = project_git(p.get('path', ''))

        # start countdown loop — redraw each second
        for countdown in range(INTERVAL, -1, -1):
            now_str = time.strftime('%Y-%m-%d  %H:%M:%S')
            sys.stdout.write(HOME_CLEAR)

            header(now_str, countdown)

            for p in projects:
                gd = git_data[p['id']]
                card(p, gd)
                rule('·', GR)

            roadmap_section(projects)
            rule('─', GR)
            print(f'{GR}  papjamzzz / creative-konsoles  ·  pipeline v1.0{R}')

            sys.stdout.flush()

            if countdown == 0:
                break
            time.sleep(1)

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\033[0m')
        sys.exit(0)
