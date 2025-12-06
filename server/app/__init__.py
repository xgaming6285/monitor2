"""
Central Monitoring Server
Flask application factory with SocketIO support
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_migrate import Migrate
import os

db = SQLAlchemy()
socketio = SocketIO()
migrate = Migrate()


def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app.config.from_object(f'app.config.{config_name.capitalize()}Config')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # Register blueprints
    from app.routes.api import api_bp
    from app.routes.websocket import register_socket_events
    
    app.register_blueprint(api_bp, url_prefix='/api')
    register_socket_events(socketio)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app

