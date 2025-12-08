"""
Database Models
"""
from datetime import datetime
from app import db
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class Computer(db.Model):
    """Registered monitored computers"""
    __tablename__ = 'computers'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    computer_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100))
    os_version = db.Column(db.String(50))
    agent_version = db.Column(db.String(20))
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    last_seen = db.Column(db.DateTime)
    is_online = db.Column(db.Boolean, default=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Device type: 'desktop' for desktop agent, 'extension' for browser extension
    device_type = db.Column(db.String(20), default='desktop')
    
    # Parent computer ID for extensions linked to desktop agents
    parent_computer_id = db.Column(db.String(36), db.ForeignKey('computers.id'), nullable=True)
    
    # Relationships
    events = db.relationship('Event', backref='computer', lazy='dynamic')
    sessions = db.relationship('Session', backref='computer', lazy='dynamic')
    extensions = db.relationship('Computer', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    
    def to_dict(self, include_extensions=False):
        result = {
            'id': self.id,
            'computer_name': self.computer_name,
            'username': self.username,
            'os_version': self.os_version,
            'agent_version': self.agent_version,
            'ip_address': self.ip_address,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_online': self.is_online,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'device_type': self.device_type,
            'parent_computer_id': self.parent_computer_id
        }
        
        if include_extensions:
            result['extensions'] = [ext.to_dict() for ext in self.extensions]
        
        return result


class Event(db.Model):
    """Core events table for all monitoring data"""
    __tablename__ = 'events'
    __table_args__ = {'sqlite_autoincrement': True}
    
    id = db.Column(db.Integer, primary_key=True)
    computer_id = db.Column(db.String(36), db.ForeignKey('computers.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, index=True)
    browser = db.Column(db.String(20))
    url = db.Column(db.Text)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'computer_id': self.computer_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'event_type': self.event_type,
            'category': self.category,
            'browser': self.browser,
            'url': self.url,
            'data': self.data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Session(db.Model):
    """User sessions on monitored computers"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    computer_id = db.Column(db.String(36), db.ForeignKey('computers.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'computer_id': self.computer_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'is_active': self.is_active
        }


class AlertRule(db.Model):
    """Configurable alert rules"""
    __tablename__ = 'alert_rules'
    __table_args__ = {'sqlite_autoincrement': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    condition = db.Column(db.JSON, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    alerts = db.relationship('Alert', backref='rule', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'condition': self.condition,
            'action': self.action,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Alert(db.Model):
    """Triggered alerts"""
    __tablename__ = 'alerts'
    __table_args__ = {'sqlite_autoincrement': True}
    
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('alert_rules.id'), nullable=False)
    computer_id = db.Column(db.String(36), db.ForeignKey('computers.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_at = db.Column(db.DateTime)
    acknowledged_by = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'computer_id': self.computer_id,
            'event_id': self.event_id,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'acknowledged': self.acknowledged,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by
        }

