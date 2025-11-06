from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class AppInfo(Base):
    __tablename__ = "app_info"
    
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True, nullable=False)
    app_name = Column(String, nullable=False)
    review_count = Column(String)
    download_count = Column(String)
    rating = Column(String, nullable=True)
    overall_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    reviews = relationship("AppReview", back_populates="app")

class AppReview(Base):
    __tablename__ = "app_review"
    
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, ForeignKey("app_info.app_id"), nullable=False)
    rating = Column(Float)
    review_content = Column(Text)
    review_date = Column(String)
    individual_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    app = relationship("AppInfo", back_populates="reviews")
