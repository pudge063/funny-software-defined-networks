#!/usr/bin/env bash
# Рендер всех *.mmd в *.svg. Требует Node.js; mermaid-cli скачивается через npx.
set -euo pipefail
cd "$(dirname "$0")"
for src in *.mmd; do
    npx -y @mermaid-js/mermaid-cli@11.4.2 -q -c mermaid.json -b white -i "$src" -o "${src%.mmd}.svg"
done
