#!/bin/bash
# CK Pipeline Widget — opens a pinned Terminal window top-right of screen

osascript <<'EOF'
tell application "Terminal"
  -- open new window running the widget
  set w to do script "python3 ~/pipeline/widget.py"

  -- position: top-right corner of primary display
  -- adjust X offset from right edge (~700px wide window)
  set bounds of front window to {1220, 25, 1920, 880}

  -- style: small font, dark profile
  set current settings of front window to settings set "Pro"

  -- smaller font so more fits
  set the font size of front window to 11

  set custom title of front window to "CK Pipeline"
  set title displays custom title of front window to true
end tell
EOF
