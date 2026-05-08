import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY       = os.getenv('SECRET_KEY', 'heritage-pantry-dev-secret-change-in-prod')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg2://postgres:Mqhe2026@localhost:5432/fcg_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY   = os.getenv('JWT_SECRET_KEY', 'fcg-jwt-dev-secret-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days
