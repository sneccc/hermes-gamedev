#!/bin/bash
# Register OpenRouter API key with OpenCode auth system
KEY=$(grep OPENROUTER_API_KEY /mnt/c/Users/Daniel/CodingProjects/hermes/gamedev_project/.env | tr -d '\r\n' | cut -d= -f2)
if [ -z "$KEY" ]; then
    echo "ERROR: Could not read OPENROUTER_API_KEY from .env"
    exit 1
fi
mkdir -p ~/.local/share/opencode
printf '{"openrouter":{"apiKey":"%s"}}' "$KEY" > ~/.local/share/opencode/auth.json
echo "Written auth.json with key: ${KEY:0:20}..."
export PATH="$HOME/.bun/bin:$HOME/.opencode/bin:$PATH"
opencode auth list
