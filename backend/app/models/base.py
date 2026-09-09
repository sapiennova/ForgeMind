"""Shared SQLAlchemy declarative base for ForgeMind domain models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by all ForgeMind SQLAlchemy models."""
