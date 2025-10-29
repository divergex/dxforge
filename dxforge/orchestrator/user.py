from typing import Optional

from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, cast
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

from orchestrator.db import User

Base = declarative_base()


class Authenticator:
    JWT_SECRET = "supersecretkey"
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = 60

    @classmethod
    def create_jwt(cls, sub: int):
        payload = {
            "sub": str(sub),  # must be string
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=Authenticator.JWT_EXPIRE_MINUTES)
        }
        return jwt.encode(payload, cls.JWT_SECRET, algorithm=cls.JWT_ALGORITHM)

    @classmethod
    def decode_jwt(cls, token: str):
        return jwt.decode(token, cls.JWT_SECRET, algorithms=[cls.JWT_ALGORITHM])

class UserManager:
    def __init__(self, db_path: str = "orchestrator.sqlite"):
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create_user(self, username: str, password: str) -> int:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        with self.Session() as s:
            if s.query(User).filter_by(username=username).first():
                raise ValueError("Username already exists")
            user = User(username=username, password_hash=hashed)
            s.add(user)
            s.commit()
            return user.id

    def authenticate(self, username: str, password: str):
        with self.Session() as s:
            user: Optional[User] = s.query(User).filter_by(username=username).first()
            if not user:
                return None
            if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                return Authenticator.create_jwt(user.id)
            return None

    def verify_jwt(self, token: str):
        try:
            payload = Authenticator.decode_jwt(token)
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            print("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print("Invalid token:", e)
            return None


if __name__ == "__main__":
    um = UserManager()
    try:
        uid = um.create_user("alice", "password123")
    except ValueError:
        print("Username already exists. Skipping...")
    token = um.authenticate("alice", "password123")
    print("JWT:", token)

    user_id = um.verify_jwt(token)
    print("User ID from token:", user_id)
