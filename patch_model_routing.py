#!/usr/bin/env python3
"""Patch OpenCode runtime's buildSpawnCommand to resolve gateway model IDs.

Overstory's resolveModel() returns a Claude alias (e.g. "sonnet") and stores the
real model in ANTHROPIC_DEFAULT_SONNET_MODEL env var. OpenCode doesn't understand
Claude aliases, so this patch extracts the real model from the env vars.
"""
import sys
import os

filepath = os.path.expanduser(
    "~/.bun/install/global/node_modules/@os-eco/overstory-cli/src/runtimes/opencode.ts"
)

with open(filepath, "r") as f:
    content = f.read()

OLD = (
    '\tbuildSpawnCommand(opts: SpawnOpts): string {\n'
    '\t\t// permissionMode, appendSystemPrompt, appendSystemPromptFile are intentionally ignored.\n'
    '\t\t// OpenCode has no equivalent flags for these options.\n'
    '\t\treturn `opencode --model ${opts.model}`;\n'
    '\t}'
)

NEW = (
    '\tbuildSpawnCommand(opts: SpawnOpts): string {\n'
    '\t\t// permissionMode, appendSystemPrompt, appendSystemPromptFile are intentionally ignored.\n'
    '\t\t// OpenCode has no equivalent flags for these options.\n'
    '\n'
    '\t\t// Resolve the actual model ID for gateway providers.\n'
    '\t\t// Overstory resolveModel returns a Claude alias (e.g. "sonnet") and puts\n'
    '\t\t// the real model in ANTHROPIC_DEFAULT_SONNET_MODEL env var. OpenCode does\n'
    '\t\t// not understand Claude aliases, so extract the real model from env.\n'
    '\t\tlet model = opts.model;\n'
    '\t\tif (opts.env) {\n'
    '\t\t\tconst aliasUpper = model.toUpperCase();\n'
    '\t\t\tconst envKey = `ANTHROPIC_DEFAULT_${aliasUpper}_MODEL`;\n'
    '\t\t\tif (opts.env[envKey]) {\n'
    '\t\t\t\tmodel = opts.env[envKey];\n'
    '\t\t\t}\n'
    '\t\t}\n'
    '\t\treturn `opencode --model ${model}`;\n'
    '\t}'
)

if OLD not in content:
    print("ERROR: buildSpawnCommand text not found — file may already be patched or changed")
    sys.exit(1)

content = content.replace(OLD, NEW)

with open(filepath, "w") as f:
    f.write(content)

print("OK: Patched buildSpawnCommand to resolve gateway model IDs")
