import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.models.grocery import Grocery
from src.services.db_service import DBService
from src.services.ws_service import ConnectionManager
from src.routes.grocery_list_routes import router as grocery_list_router
from src.routes.user_routes import router as user_router
from src.routes.recipe_routes import router as recipe_router
from src.routes.dropbox_routes import router as dropbox_router
from src.routes.meal_plan_routes import router as meal_plan_router

app = FastAPI()
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
db = DBService(mongo_uri, "whatdoweeat")
manager = ConnectionManager()

def get_db():
    return db

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(grocery_list_router)
app.include_router(user_router)
app.include_router(recipe_router)
app.include_router(dropbox_router)
app.include_router(meal_plan_router)

@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket, code)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, code)
