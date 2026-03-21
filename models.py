import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, Text, LargeBinary, DateTime

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GeneratedImage(Base):
    __tablename__ = "images"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    prompt = Column(Text, nullable=False)
    provider = Column(String(50), nullable=False)
    model_key = Column(String(100), nullable=False)
    model_name = Column(String(200), nullable=False, default="")
    image_data = Column(LargeBinary, nullable=False)
    user_id = Column(String, nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=False)
    share_token = Column(String(32), unique=True, nullable=True, index=True)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ImageTag(Base):
    __tablename__ = "image_tags"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    image_id = Column(String, nullable=False, index=True)
    tag = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
