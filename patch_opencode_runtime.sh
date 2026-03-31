#!/bin/bash
# Patch OpenCode runtime adapter in overstory:
# 1. detectReady: detect "Ask anything" / "Build" strings in TUI
# 2. buildSpawnCommand: resolve gateway model IDs from env vars
OFILE="$HOME/.bun/install/global/node_modules/@os-eco/overstory-cli/src/runtimes/opencode.ts"

# Use python3 for reliable text replacement
python3 -c "
import sys
with open(sys.argv[1], 'r') as f:
    content = f.read()

old = '''detectReady(_paneContent: string): ReadyState {
\t\t// STUB: Real OpenCode TUI ready patterns have not been observed.
\t\t// Fill in once someone runs OpenCode in tmux and captures the pane content.
\t\treturn { phase: \"loading\" };
\t}'''

new = '''detectReady(paneContent: string): ReadyState {
\t\t// Detect OpenCode TUI ready state from tmux pane content.
\t\t// OpenCode shows 'Ask anything' prompt and 'Build' label when ready.
\t\tif (paneContent.includes('Ask anything') || paneContent.includes('Build')) {
\t\t\treturn { phase: 'ready' };
\t\t}
\t\treturn { phase: 'loading' };
\t}'''

if old in content:
    content = content.replace(old, new)
    with open(sys.argv[1], 'w') as f:
        f.write(content)
    print('SUCCESS: Patched detectReady')
else:
    print('WARNING: Old pattern not found, trying tab-agnostic match...')
    # Try without specific tab patterns
    import re
    pattern = r'detectReady\(_paneContent: string\): ReadyState \{[^}]*return \{ phase: \"loading\" \};[^}]*\}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        content = content[:match.start()] + '''detectReady(paneContent: string): ReadyState {
\t\tif (paneContent.includes(\"Ask anything\") || paneContent.includes(\"Build\")) {
\t\t\treturn { phase: \"ready\" };
\t\t}
\t\treturn { phase: \"loading\" };
\t}''' + content[match.end():]
        with open(sys.argv[1], 'w') as f:
            f.write(content)
        print('SUCCESS: Patched detectReady (regex)')
    else:
        print('FAIL: Could not find detectReady to patch')
        sys.exit(1)
" "$OFILE"

# --- Patch 2: buildSpawnCommand gateway model resolution ---
python3 /mnt/c/Users/Daniel/CodingProjects/hermes/gamedev_project/patch_model_routing.py
