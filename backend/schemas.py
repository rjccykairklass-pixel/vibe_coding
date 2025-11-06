from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AppInfoCreate(BaseModel):
    app_id: str

class AppInfoResponse(BaseModel):
    id: int
    app_id: str
    app_name: str
    review_count: str
    download_count: str
    rating: Optional[str] = None
    overall_analysis: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AppReviewResponse(BaseModel):
    id: int
    app_id: str
    rating: float
    review_content: str
    review_date: str
    individual_analysis: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AppDetailResponse(BaseModel):
    app_info: AppInfoResponse
    reviews: List[AppReviewResponse]
    
class AnalyzeRequest(BaseModel):
    app_id: str
