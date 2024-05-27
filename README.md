# whatdoweeat
A project to manage a recipe database, a meal planner and a grocery list all at once in order to answer the inevitable question "what do we eat ?"

## How to start locally

You need to have python3 node and mogoDB installed. You can either follow the below steps or if you have tmux on a linux machine you can run the start.sh script in the root folder, it will create a tmux session with 3 windows :

- 0. the backend
- 1. the frontend
- 2. the database

use ctrl+b and the window number to switch. To kill all the processes use tmux kill-server or tmux kill-session -t whatdoweeat.


### backend

1. Go to back folder
2. Create a venv if not created already (python -m venv .venv for linux, python -m venv venv for windows)
3. Activate the venv (source .venv/bin/activate for linux, .\venv\Scripts\activate for windows)
4. Install dependencies on the venv :
```
pip install --no-cache-dir -r requirements.txt
```
5. run fastAPI with uvicorn : 
```
uvicorn main:app --reload
```

### frontend

1. Go to front folder
2. run npm install
3. run npm run dev

### database

mongod --dbpath /path/to/the/db/directory




