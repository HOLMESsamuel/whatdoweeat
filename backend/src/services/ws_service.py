from fastapi import WebSocket

class ConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectionManager, cls).__new__(cls)
            cls._instance.active_connections = {}
        return cls._instance

    async def connect(self, websocket: WebSocket, id: str):
        await websocket.accept()
        if id not in self.active_connections:
            self.active_connections[id] = []
        self.active_connections[id].append(websocket)

    def disconnect(self, websocket: WebSocket, id: str):
        if id in self.active_connections:
            self.active_connections[id].remove(websocket)
            if not self.active_connections[id]:
                del self.active_connections[id]

    async def broadcast(self, message: str, id: str):
        if id in self.active_connections:
            for connection in self.active_connections[id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error sending message: {e}")
        else:
            print("No connection found for id")