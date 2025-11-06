import google.generativeai as genai
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. backend/.env 파일을 확인하세요.")

genai.configure(api_key=GEMINI_API_KEY)

def analyze_reviews_overall(reviews: List[Dict]) -> str:
    """전체 리뷰를 분석합니다."""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 리뷰 텍스트 조합
    reviews_text = "\n\n".join([
        f"별점: {review['rating']}점\n날짜: {review['review_date']}\n내용: {review['review_content']}"
        for review in reviews
    ])
    
    prompt = f"""
다음은 앱에 대한 사용자 리뷰들입니다. 전체적인 분석을 제공해주세요.

{reviews_text}

다음 항목들을 포함하여 분석해주세요:
1. 전반적인 사용자 만족도
2. 주요 긍정적 피드백 (3가지)
3. 주요 부정적 피드백 (3가지)
4. 개선 제안사항
5. 전체 요약

분석 결과를 한국어로 작성해주세요.
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"전체 분석 실패: {str(e)}"

def analyze_review_individual(review: Dict) -> str:
    """개별 리뷰를 분석합니다."""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
다음 앱 리뷰를 분석해주세요:

별점: {review['rating']}점
날짜: {review['review_date']}
내용: {review['review_content']}

다음 항목들을 간단히 분석해주세요:
1. 감정 분석 (긍정/부정/중립)
2. 주요 언급 내용 (기능, 성능, UI/UX, 버그 등)
3. 핵심 요약 (1-2문장)

분석 결과를 한국어로 간결하게 작성해주세요.
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"개별 분석 실패: {str(e)}"

def analyze_all_reviews(reviews: List[Dict]) -> tuple[str, List[str]]:
    """
    전체 리뷰와 개별 리뷰를 모두 분석합니다.
    Returns: (전체 분석 결과, 개별 분석 결과 리스트)
    """
    overall_analysis = analyze_reviews_overall(reviews)
    
    individual_analyses = []
    for review in reviews:
        individual_analysis = analyze_review_individual(review)
        individual_analyses.append(individual_analysis)
    
    return overall_analysis, individual_analyses
