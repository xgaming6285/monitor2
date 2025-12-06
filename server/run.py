"""
Server Entry Point
"""
from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("  MONITOR SERVER")
    print("  Central Monitoring Dashboard")
    print("=" * 50)
    print("\n  API: http://localhost:5000/api")
    print("  WebSocket: ws://localhost:5000/live")
    print("  Health: http://localhost:5000/api/health")
    print("\n" + "=" * 50)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

