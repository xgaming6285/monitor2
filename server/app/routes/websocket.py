"""
WebSocket Handlers for Live Updates
"""
from flask_socketio import emit, join_room, leave_room
from datetime import datetime


def register_socket_events(socketio):
    """Register all WebSocket event handlers"""
    
    @socketio.on('connect', namespace='/live')
    def handle_connect():
        """Handle new dashboard connection"""
        print(f"Dashboard connected: {datetime.utcnow().isoformat()}")
        emit('connected', {
            'message': 'Connected to live feed',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @socketio.on('disconnect', namespace='/live')
    def handle_disconnect():
        """Handle dashboard disconnection"""
        print(f"Dashboard disconnected: {datetime.utcnow().isoformat()}")
    
    @socketio.on('subscribe_computer', namespace='/live')
    def handle_subscribe(data):
        """Subscribe to events from a specific computer"""
        computer_id = data.get('computer_id')
        if computer_id:
            join_room(f'computer_{computer_id}')
            emit('subscribed', {
                'computer_id': computer_id,
                'message': f'Subscribed to computer {computer_id}'
            })
    
    @socketio.on('unsubscribe_computer', namespace='/live')
    def handle_unsubscribe(data):
        """Unsubscribe from a specific computer's events"""
        computer_id = data.get('computer_id')
        if computer_id:
            leave_room(f'computer_{computer_id}')
            emit('unsubscribed', {
                'computer_id': computer_id,
                'message': f'Unsubscribed from computer {computer_id}'
            })
    
    @socketio.on('subscribe_all', namespace='/live')
    def handle_subscribe_all():
        """Subscribe to events from all computers"""
        join_room('all_events')
        emit('subscribed', {
            'message': 'Subscribed to all computer events'
        })
    
    @socketio.on('ping', namespace='/live')
    def handle_ping():
        """Handle ping for connection keep-alive"""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat()
        })

