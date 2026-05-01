#!/bin/bash

# Kill anything still listening on the dev ports from a previous run.
# Targeting ports rather than process names avoids killing unrelated
# mongod / node processes you might have running.
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "🛑 Killing process(es) on port $port: $pids"
    kill -TERM $pids 2>/dev/null || true
    sleep 1
    # Anything still alive gets the hammer.
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      kill -KILL $pids 2>/dev/null || true
    fi
  fi
}

kill_port 27017   # MongoDB
kill_port 8000    # backend (uvicorn)
kill_port 5173    # frontend (vite)

# Lancer MongoDB (si pas déjà en cours)
mongod --dbpath ./db &> /tmp/mongod.log &
MONGOD_PID=$!

# Attendre MongoDB
sleep 3

# Path to the Obsidian recipe folder. Used only for the single-tenant
# fallback (RECIPE_SOURCE=local on /recipes). The per-user routes read
# from each user's own Dropbox, not from this folder.
RECIPES_DIR="${RECIPES_DIR:-$HOME/Dropbox/ideaverse/Recettes/recette-templated}"

# Friendly heads-up if the dev secrets file is missing.
if [ ! -f "$PWD/.env.dev" ]; then
  echo "⚠️  .env.dev not found — copy .env.dev.example to .env.dev and fill"
  echo "    in DROPBOX_APP_KEY / SECRET / TOKEN_ENC_KEY before testing the"
  echo "    Connect Dropbox flow. Auth-only endpoints will work without it."
fi

# Backend in a new Terminal tab. We have the new tab `set -a; source
# .env.dev; set +a` so every var in the file becomes a real environment
# variable for uvicorn — no need to enumerate them here.
osascript -e 'tell app "Terminal"
  do script "cd \"'$PWD'\"
; set -a; [ -f .env.dev ] && source .env.dev; set +a; export RECIPES_DIR=\"'"$RECIPES_DIR"'\"; cd backend; python3 -m venv .venv 2>/dev/null; source .venv/bin/activate; pip install -q -r requirements.txt; uvicorn main:app --reload --port 8000"
end tell'

# Frontend dans un nouvel onglet
osascript -e 'tell app "Terminal"
  do script "cd \"'$PWD/frontend'\"
; npm install; npm run dev"
end tell'

echo "✅ MongoDB: localhost:27017"
echo "✅ Backend: http://localhost:8000"
echo "✅ Frontend: http://localhost:5173"
