import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "super_secret_key_12345")
    
    API_TOEKN = ("my-agent-secret")

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL

    SQLALCHEMY_TRACK_MODIFICATIONS = False