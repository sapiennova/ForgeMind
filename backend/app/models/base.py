"""Shared SQLAlchemy declarative base for ForgeMind domain models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ForgeMind SQLAlchemy models."""
