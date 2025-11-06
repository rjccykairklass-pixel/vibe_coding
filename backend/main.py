from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import asyncio
from contextlib import asynccontextmanager

from database import get_db, init_db
from models import AppInfo, AppReview
from schemas import (
    AppInfoCreate, 
    AppInfoResponse, 
    AppReviewResponse, 
    AppDetailResponse,
    AnalyzeRequest
)
from crawler import crawl_app_info, crawl_app_reviews
from gemini_analyzer import analyze_all_reviews
from topic_modeling import perform_topic_modeling

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (필요시 정리 작업 추가)

app = FastAPI(title="App Review Analyzer", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "App Review Analyzer API"}

@app.post("/api/apps/crawl", response_model=AppDetailResponse)
async def crawl_app(app_data: AppInfoCreate, db: Session = Depends(get_db)):
    """앱 정보와 리뷰를 크롤링하여 저장합니다."""
    try:
        # 이미 존재하는지 확인
        existing_app = db.query(AppInfo).filter(AppInfo.app_id == app_data.app_id).first()
        if existing_app:
            # 이미 등록된 앱이면 기존 데이터 반환
            reviews = db.query(AppReview).filter(AppReview.app_id == app_data.app_id).all()
            return AppDetailResponse(
                app_info=AppInfoResponse.from_orm(existing_app),
                reviews=[AppReviewResponse.from_orm(r) for r in reviews]
            )
        
        # 1. 앱 정보 크롤링
        app_info_data = await crawl_app_info(app_data.app_id)
        
        # 2. 앱 정보 저장
        app_info = AppInfo(
            app_id=app_info_data["app_id"],
            app_name=app_info_data["app_name"],
            review_count=app_info_data["review_count"],
            download_count=app_info_data["download_count"],
            rating=app_info_data.get("rating", "정보 없음")
        )
        db.add(app_info)
        db.commit()
        db.refresh(app_info)
        
        # 3. 리뷰 크롤링
        reviews_data = await crawl_app_reviews(app_data.app_id, max_reviews=10)
        
        # 4. 리뷰 저장
        reviews = []
        for review_data in reviews_data:
            review = AppReview(
                app_id=app_data.app_id,
                rating=review_data["rating"],
                review_content=review_data["review_content"],
                review_date=review_data["review_date"]
            )
            db.add(review)
            reviews.append(review)
        
        db.commit()
        for review in reviews:
            db.refresh(review)
        
        return AppDetailResponse(
            app_info=AppInfoResponse.from_orm(app_info),
            reviews=[AppReviewResponse.from_orm(r) for r in reviews]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/apps", response_model=List[AppInfoResponse])
def get_apps(db: Session = Depends(get_db)):
    """모든 앱 정보를 조회합니다."""
    apps = db.query(AppInfo).all()
    return apps

@app.get("/api/apps/{app_id}", response_model=AppDetailResponse)
def get_app_detail(app_id: str, db: Session = Depends(get_db)):
    """특정 앱의 상세 정보와 리뷰를 조회합니다."""
    app = db.query(AppInfo).filter(AppInfo.app_id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다.")
    
    reviews = db.query(AppReview).filter(AppReview.app_id == app_id).all()
    
    return AppDetailResponse(
        app_info=AppInfoResponse.from_orm(app),
        reviews=[AppReviewResponse.from_orm(r) for r in reviews]
    )

@app.post("/api/apps/analyze")
def analyze_app_reviews(request: AnalyzeRequest, db: Session = Depends(get_db)):
    """앱 리뷰를 AI로 분석합니다."""
    try:
        # 앱 정보 조회
        app = db.query(AppInfo).filter(AppInfo.app_id == request.app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다.")
        
        # 리뷰 조회
        reviews = db.query(AppReview).filter(AppReview.app_id == request.app_id).all()
        if not reviews:
            raise HTTPException(status_code=404, detail="분석할 리뷰가 없습니다.")
        
        # 리뷰 데이터를 딕셔너리로 변환
        reviews_data = [
            {
                "rating": r.rating,
                "review_content": r.review_content,
                "review_date": r.review_date
            }
            for r in reviews
        ]
        
        # Gemini API로 분석
        overall_analysis, individual_analyses = analyze_all_reviews(reviews_data)
        
        # 전체 분석 결과 저장
        app.overall_analysis = overall_analysis
        
        # 개별 분석 결과 저장
        for review, analysis in zip(reviews, individual_analyses):
            review.individual_analysis = analysis
        
        db.commit()
        
        return {
            "message": "분석이 완료되었습니다.",
            "overall_analysis": overall_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/apps/{app_id}")
def delete_app(app_id: str, db: Session = Depends(get_db)):
    """앱 정보와 관련 리뷰를 삭제합니다."""
    app = db.query(AppInfo).filter(AppInfo.app_id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다.")
    
    # 관련 리뷰 먼저 삭제
    db.query(AppReview).filter(AppReview.app_id == app_id).delete()
    
    # 앱 정보 삭제
    db.delete(app)
    db.commit()
    
    return {"message": "앱이 삭제되었습니다."}

@app.post("/api/apps/{app_id}/topic-modeling")
def topic_modeling_app(app_id: str, db: Session = Depends(get_db)):
    """앱 리뷰에 대한 토픽 모델링을 수행하고 t-SNE 결과를 반환합니다."""
    try:
        # 앱 정보 조회
        app = db.query(AppInfo).filter(AppInfo.app_id == app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다.")
        
        # 리뷰 조회
        reviews = db.query(AppReview).filter(AppReview.app_id == app_id).all()
        if not reviews:
            raise HTTPException(status_code=404, detail="분석할 리뷰가 없습니다.")
        
        # 리뷰 데이터를 딕셔너리로 변환
        reviews_data = [
            {
                "rating": r.rating,
                "review_content": r.review_content,
                "review_date": r.review_date
            }
            for r in reviews
        ]
        
        # 토픽 모델링 수행
        result = perform_topic_modeling(reviews_data)
        
        if "error" in result:
            return result
        
        return {
            "app_name": app.app_name,
            "topics": result["topics"],
            "tsne_data": result["tsne_data"],
            "n_reviews": result["n_reviews"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
