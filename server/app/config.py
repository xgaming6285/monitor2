"""
Server Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    
    # Event batching
    EVENT_BATCH_SIZE = 100
    EVENT_BATCH_TIMEOUT = 5  # seconds


class DevelopmentConfig(BaseConfig):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///monitor.db'  # SQLite for easy development
    )


class ProductionConfig(BaseConfig):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # Stricter security in production
    SECRET_KEY = os.getenv('SECRET_KEY', 'prod-secret-change-me')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'prod-jwt-change-me')


class TestingConfig(BaseConfig):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

