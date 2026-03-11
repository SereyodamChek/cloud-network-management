import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "super_secret_key_12345")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://Dom:Dom%401304@127.0.0.1:3307/network_management"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False