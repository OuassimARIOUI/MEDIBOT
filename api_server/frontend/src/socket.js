/**
 * Socket.IO client singleton
 * ==========================
 *
 * Maintains a single WebSocket connection to the Flask-SocketIO backend.
 */

import { io } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace('/api', '')
  : 'http://localhost:5000';

const socket = io(SOCKET_URL, {
  autoConnect: true,
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 2000,
});

socket.on('connect', () => {
  console.log('🔌 WebSocket connecté');
});

socket.on('disconnect', (reason) => {
  console.log('🔌 WebSocket déconnecté:', reason);
});

export default socket;
