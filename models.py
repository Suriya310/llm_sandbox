from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class PromptAttempt(Base):
    __tablename__ = "prompt_attempts"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # IPv6 compatible
    prompt_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex digest
    user_prompt = Column(Text, nullable=False)
    llm_response = Column(Text, nullable=True)
    is_injection_detected = Column(Boolean, default=False, nullable=False)
    flag_revealed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Index on prompt_hash is already created via unique=True above.
    # Additional indexes for common query patterns:
    # - (ip_address, created_at) for rate limiting window queries
    # - flag_revealed for analytics on successful challenges
    __table_args__ = (
        Index('idx_ip_created', 'ip_address', 'created_at'),
        Index('idx_flag_revealed', 'flag_revealed'),
    )