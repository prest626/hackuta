import { WebSocketServer } from 'ws';

// Offline convai socket. `script` is sent after the client's first message (init, then server events).
export function listen(script = []) {
  const wss = new WebSocketServer({ port: 0, host: '127.0.0.1' });
  const messages = [];
  const clients = new Set();
  const send = (event) => {
    const raw = JSON.stringify(event);
    for (const ws of clients) if (ws.readyState === 1) ws.send(raw);
  };
  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('error', () => {});
    let primed = false;
    ws.on('message', (data) => {
      const raw = data.toString();
      try {
        messages.push(JSON.parse(raw));
      } catch {
        messages.push(raw);
      }
      if (!primed) {
        primed = true;
        for (const event of script) ws.send(JSON.stringify(event));
      }
    });
    ws.on('close', () => clients.delete(ws));
  });
  return new Promise((resolve) => {
    wss.once('listening', () => {
      const { port } = wss.address();
      resolve({
        url: `ws://127.0.0.1:${port}`,
        messages,
        send,
        close: () => new Promise((done) => wss.close(done)),
      });
    });
  });
}
