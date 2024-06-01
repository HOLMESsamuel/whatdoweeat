from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.models.grocery import Grocery
from src.services.db_service import DBService
from src.services.ws_service import ConnectionManager
from src.routes.grocery_list_routes import router as grocery_list_router
from src.routes.user_routes import router as user_router

app = FastAPI()
db = DBService("mongodb://localhost:27017", "whatdoweeat")
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

#@app.delete("/grocery/{name}")
#async def delete_grocery(name: str, db: DBService = Depends(get_db)):
#    await db.delete_grocery(name)
#    await manager.broadcast(f"Grocery item deleted: {name}")
#    return {"message": "Grocery item deleted"}

@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
