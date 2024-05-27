#!/bin/bash

# start new tmux session called whatdoweeat
tmux new-session -d -s whatdoweeat

# configure and start backend on window 0
tmux send-keys -t whatdoweeat 'cd backend' C-m
tmux send-keys -t whatdoweeat 'if [ ! -d ".venv" ]; then python3 -m venv .venv; fi' C-m
tmux send-keys -t whatdoweeat 'source .venv/bin/activate' C-m
tmux send-keys -t whatdoweeat 'pip install --no-cache-dir -r requirements.txt' C-m
tmux send-keys -t whatdoweeat 'uvicorn main:app --reload' C-m

# configure and start frontend on window 1
tmux new-window -t whatdoweeat:1
tmux send-keys -t whatdoweeat:1 'cd frontend' C-m
tmux send-keys -t whatdoweeat:1 'npm install' C-m
tmux send-keys -t whatdoweeat:1 'npm run dev' C-m

# start database on window 2
tmux new-window -t whatdoweeat:2
tmux send-keys -t whatdoweeat:2 'mongod --dbpath db' C-m

# Attach tmux session
tmux attach-session -t whatdoweeat


