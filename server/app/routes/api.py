"""
REST API Endpoints
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import secrets
import jwt

from app import db, socketio
from app.models import Computer, Event, Session, AlertRule, Alert
from app.config import BaseConfig

api_bp = Blueprint('api', __name__)


def generate_api_key():
    """Generate a unique API key for agent authentication"""
    return secrets.token_hex(32)


def require_api_key(f):
    """Decorator to require valid API key for agent endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        computer = Computer.query.filter_by(api_key=api_key).first()
        if not computer:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Update last seen
        computer.last_seen = datetime.utcnow()
        computer.is_online = True
        db.session.commit()
        
        return f(computer, *args, **kwargs)
    return decorated


# ============== Agent Endpoints ==============

@api_bp.route('/register', methods=['POST'])
def register_computer():
    """
    Register a new monitored computer
    
    Request body:
    {
        "computer_name": "PC-SALES-001",
        "username": "john.doe",
        "os_version": "Windows 10 Pro",
        "agent_version": "1.0.0"
    }
    """
    data = request.get_json()
    
    if not data or 'computer_name' not in data:
        return jsonify({'error': 'computer_name is required'}), 400
    
    # Generate unique API key
    api_key = generate_api_key()
    
    computer = Computer(
        computer_name=data['computer_name'],
        username=data.get('username'),
        os_version=data.get('os_version'),
        agent_version=data.get('agent_version'),
        ip_address=request.remote_addr,
        api_key=api_key,
        last_seen=datetime.utcnow(),
        is_online=True
    )
    
    db.session.add(computer)
    db.session.commit()
    
    # Emit to connected dashboards
    socketio.emit('computer_registered', computer.to_dict(), namespace='/live')
    
    return jsonify({
        'success': True,
        'computer_id': computer.id,
        'api_key': api_key,
        'message': 'Computer registered successfully'
    }), 201


@api_bp.route('/events', methods=['POST'])
@require_api_key
def receive_events(computer):
    """
    Receive events from agent (supports batch)
    
    Request body:
    {
        "events": [
            {
                "timestamp": "2024-12-06T14:32:15.234Z",
                "event_type": "keystroke",
                "category": "input",
                "data": {...}
            }
        ]
    }
    """
    data = request.get_json()
    
    if not data or 'events' not in data:
        return jsonify({'error': 'events array is required'}), 400
    
    events_data = data['events']
    if not isinstance(events_data, list):
        events_data = [events_data]
    
    created_events = []
    
    for event_data in events_data:
        try:
            # Parse timestamp
            timestamp = event_data.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                timestamp = datetime.utcnow()
            
            event = Event(
                computer_id=computer.id,
                timestamp=timestamp,
                event_type=event_data.get('event_type', 'unknown'),
                category=event_data.get('category', 'unknown'),
                browser=event_data.get('browser'),
                url=event_data.get('url'),
                data=event_data.get('data', {})
            )
            
            db.session.add(event)
            created_events.append(event)
            
        except Exception as e:
            # Log error but continue processing other events
            print(f"Error processing event: {e}")
            continue
    
    db.session.commit()
    
    # Emit events to connected dashboards in real-time
    for event in created_events:
        event_dict = event.to_dict()
        event_dict['computer_name'] = computer.computer_name
        socketio.emit('new_event', event_dict, namespace='/live')
    
    return jsonify({
        'success': True,
        'processed': len(created_events),
        'total': len(events_data)
    })


@api_bp.route('/heartbeat', methods=['POST'])
@require_api_key
def heartbeat(computer):
    """
    Agent health check - updates last_seen timestamp
    """
    data = request.get_json() or {}
    
    # Update computer status
    computer.is_online = True
    computer.last_seen = datetime.utcnow()
    
    if 'agent_version' in data:
        computer.agent_version = data['agent_version']
    
    db.session.commit()
    
    # Emit status update
    socketio.emit('computer_status', {
        'computer_id': computer.id,
        'is_online': True,
        'last_seen': computer.last_seen.isoformat()
    }, namespace='/live')
    
    return jsonify({
        'success': True,
        'timestamp': datetime.utcnow().isoformat()
    })


@api_bp.route('/live-keystroke', methods=['POST'])
@require_api_key
def receive_live_keystroke(computer):
    """
    Receive a single live keystroke for real-time streaming.
    This is optimized for low-latency delivery to dashboards.
    
    Request body:
    {
        "timestamp": "2024-12-06T14:32:15.234Z",
        "event_type": "live_keystroke",
        "category": "input",
        "data": {
            "key": "a",
            "target_window": "Chrome - Google",
            "target_process": "chrome.exe"
        }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Event data required'}), 400
    
    # Build the live keystroke event
    live_event = {
        'computer_id': computer.id,
        'computer_name': computer.computer_name,
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
        'event_type': 'live_keystroke',
        'data': data.get('data', {})
    }
    
    # Emit immediately to all connected dashboards
    # Emit to specific computer room for targeted subscriptions
    socketio.emit('live_keystroke', live_event, namespace='/live', room=f'computer_{computer.id}')
    
    # Also emit to 'all_events' room for dashboards monitoring everything
    socketio.emit('live_keystroke', live_event, namespace='/live', room='all_events')
    
    return jsonify({'success': True})


# ============== Dashboard Endpoints ==============

@api_bp.route('/computers', methods=['GET'])
def list_computers():
    """Get list of all registered computers"""
    computers = Computer.query.order_by(Computer.registered_at.desc()).all()
    
    # Update online status based on last_seen
    timeout = datetime.utcnow() - timedelta(minutes=2)
    for computer in computers:
        if computer.last_seen and computer.last_seen < timeout:
            computer.is_online = False
    
    db.session.commit()
    
    return jsonify({
        'computers': [c.to_dict() for c in computers],
        'total': len(computers)
    })


@api_bp.route('/computers/<computer_id>', methods=['GET'])
def get_computer(computer_id):
    """Get details of a specific computer"""
    computer = Computer.query.get_or_404(computer_id)
    return jsonify(computer.to_dict())


@api_bp.route('/events', methods=['GET'])
def get_events():
    """
    Query events with filters
    
    Query params:
    - computer_id: Filter by computer
    - event_type: Filter by event type
    - category: Filter by category
    - start: Start timestamp (ISO format)
    - end: End timestamp (ISO format)
    - limit: Max results (default 100)
    - offset: Pagination offset
    - search: Full-text search in data
    """
    query = Event.query
    
    # Apply filters
    computer_id = request.args.get('computer_id')
    if computer_id:
        query = query.filter(Event.computer_id == computer_id)
    
    event_type = request.args.get('event_type')
    if event_type:
        query = query.filter(Event.event_type == event_type)
    
    category = request.args.get('category')
    if category:
        query = query.filter(Event.category == category)
    
    start = request.args.get('start')
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            query = query.filter(Event.timestamp >= start_dt)
        except ValueError:
            pass
    
    end = request.args.get('end')
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            query = query.filter(Event.timestamp <= end_dt)
        except ValueError:
            pass
    
    # Pagination
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))
    
    # Order by timestamp descending (most recent first)
    query = query.order_by(Event.timestamp.desc())
    
    total = query.count()
    events = query.limit(limit).offset(offset).all()
    
    # Include computer name in response
    result = []
    for event in events:
        event_dict = event.to_dict()
        event_dict['computer_name'] = event.computer.computer_name
        result.append(event_dict)
    
    return jsonify({
        'events': result,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@api_bp.route('/sessions', methods=['GET'])
def get_sessions():
    """Get user sessions"""
    computer_id = request.args.get('computer_id')
    
    query = Session.query
    if computer_id:
        query = query.filter(Session.computer_id == computer_id)
    
    sessions = query.order_by(Session.started_at.desc()).limit(100).all()
    
    return jsonify({
        'sessions': [s.to_dict() for s in sessions]
    })


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get analytics and statistics"""
    # Overall stats
    total_computers = Computer.query.count()
    online_computers = Computer.query.filter_by(is_online=True).count()
    total_events = Event.query.count()
    
    # Events in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    events_24h = Event.query.filter(Event.timestamp >= yesterday).count()
    
    # Events by category
    from sqlalchemy import func
    category_stats = db.session.query(
        Event.category,
        func.count(Event.id)
    ).group_by(Event.category).all()
    
    # Events by type
    type_stats = db.session.query(
        Event.event_type,
        func.count(Event.id)
    ).group_by(Event.event_type).order_by(func.count(Event.id).desc()).limit(10).all()
    
    return jsonify({
        'total_computers': total_computers,
        'online_computers': online_computers,
        'total_events': total_events,
        'events_24h': events_24h,
        'events_by_category': {cat: count for cat, count in category_stats},
        'top_event_types': {et: count for et, count in type_stats}
    })


# ============== Alert Endpoints ==============

@api_bp.route('/alerts/rules', methods=['GET', 'POST'])
def alert_rules():
    """Get or create alert rules"""
    if request.method == 'GET':
        rules = AlertRule.query.all()
        return jsonify({'rules': [r.to_dict() for r in rules]})
    
    data = request.get_json()
    rule = AlertRule(
        name=data['name'],
        description=data.get('description'),
        condition=data['condition'],
        action=data.get('action', 'notify'),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify(rule.to_dict()), 201


@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Get triggered alerts"""
    acknowledged = request.args.get('acknowledged')
    
    query = Alert.query
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged == (acknowledged.lower() == 'true'))
    
    alerts = query.order_by(Alert.triggered_at.desc()).limit(100).all()
    
    return jsonify({
        'alerts': [a.to_dict() for a in alerts]
    })


# ============== Health Check ==============

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Server health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

