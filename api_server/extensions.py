"""Extensions Flask partagées (évite les imports circulaires)."""

from flask_socketio import SocketIO

socketio = SocketIO()
