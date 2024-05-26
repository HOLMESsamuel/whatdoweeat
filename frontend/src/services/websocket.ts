export class WebSocketService {
    private socket: WebSocket | null = null;
  
    constructor(private url: string) {}
  
    connect(onMessage: (event: MessageEvent) => void) {
      this.socket = new WebSocket(this.url);
      this.socket.onmessage = onMessage;
      this.socket.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        setTimeout(() => this.connect(onMessage), 1000);
      };
    }
  
    sendMessage(message: string) {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(message);
      } else {
        console.error('WebSocket is not open');
      }
    }
  }