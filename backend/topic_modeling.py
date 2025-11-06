# -*- coding: utf-8 -*-
"""
토픽 모델링 및 t-SNE 시각화 모듈
"""
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.manifold import TSNE
from typing import List, Dict
import re

# KoNLPy 임포트 (명사 추출용)
okt = None
KONLPY_AVAILABLE = False
try:
    from konlpy.tag import Okt
    okt = Okt()
    KONLPY_AVAILABLE = True
except Exception as e:
    print(f"Warning: KoNLPy not available ({e}). Using simple tokenizer instead.")

def preprocess_korean_text(text: str) -> str:
    """한글 텍스트 전처리"""
    # 특수문자 제거, 한글과 공백만 남김
    text = re.sub(r'[^가-힣\s]', ' ', text)
    # 여러 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_nouns(text: str) -> List[str]:
    """한글 텍스트에서 명사만 추출"""
    if KONLPY_AVAILABLE and okt is not None:
        try:
            # Okt를 사용하여 명사 추출
            nouns = okt.nouns(text)
            # 2글자 이상의 명사만 반환
            return [noun for noun in nouns if len(noun) >= 2]
        except Exception as e:
            print(f"Warning: Noun extraction failed: {e}")
            # 실패 시 fallback
            words = text.split()
            return [word for word in words if len(word) >= 2]
    else:
        # KoNLPy가 없을 경우 간단한 규칙 기반 명사 추출
        # 일반적인 한글 명사 패턴 (조사 제거)
        common_particles = ['은', '는', '이', '가', '을', '를', '의', '에', '에서', '으로', '로', '와', '과', '도', '만', '라도', '부터', '까지']
        words = text.split()
        nouns = []
        for word in words:
            if len(word) < 2:
                continue
            # 조사 제거 시도
            noun = word
            for particle in common_particles:
                if word.endswith(particle) and len(word) > len(particle) + 1:
                    noun = word[:-len(particle)]
                    break
            if len(noun) >= 2:
                nouns.append(noun)
        return nouns if nouns else [word for word in words if len(word) >= 2]

def perform_topic_modeling(reviews: List[Dict], n_topics: int = 5) -> Dict:
    """
    토픽 모델링 수행 및 t-SNE 좌표 반환
    
    Args:
        reviews: 리뷰 데이터 리스트 (각 딕셔너리는 review_content 키 필요)
        n_topics: 토픽 개수
    
    Returns:
        토픽 모델링 결과 및 t-SNE 좌표
    """
    # 리뷰 텍스트 추출 및 전처리
    texts = [preprocess_korean_text(review['review_content']) for review in reviews]
    
    # 빈 텍스트 제거
    valid_indices = [i for i, text in enumerate(texts) if text.strip()]
    if len(valid_indices) < 3:
        return {
            "error": "분석 가능한 리뷰가 부족합니다 (최소 3개 필요)",
            "topics": [],
            "tsne_data": []
        }
    
    texts = [texts[i] for i in valid_indices]
    valid_reviews = [reviews[i] for i in valid_indices]
    
    # TF-IDF 벡터화 (명사만 사용)
    vectorizer = TfidfVectorizer(
        tokenizer=extract_nouns,
        max_features=100,
        min_df=1,
        max_df=0.8,
        ngram_range=(1, 2)
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except Exception as e:
        return {
            "error": f"벡터화 실패: {str(e)}",
            "topics": [],
            "tsne_data": []
        }
    
    # LDA 토픽 모델링
    n_topics = min(n_topics, len(texts) // 2, 10)  # 토픽 수 조정
    if n_topics < 2:
        n_topics = 2
    
    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20
    )
    
    try:
        lda_matrix = lda.fit_transform(tfidf_matrix)
    except Exception as e:
        return {
            "error": f"토픽 모델링 실패: {str(e)}",
            "topics": [],
            "tsne_data": []
        }
    
    # 토픽별 주요 단어 추출
    feature_names = vectorizer.get_feature_names_out()
    topics = []
    for topic_idx, topic in enumerate(lda.components_):
        top_indices = topic.argsort()[-5:][::-1]
        top_words = [feature_names[i] for i in top_indices]
        topics.append({
            "topic_id": topic_idx,
            "top_words": top_words
        })
    
    # 각 리뷰의 주 토픽 할당
    doc_topics = np.argmax(lda_matrix, axis=1)
    
    # t-SNE로 2차원 축소
    if tfidf_matrix.shape[0] >= 3:
        perplexity = min(30, tfidf_matrix.shape[0] - 1)
        tsne = TSNE(
            n_components=2,
            random_state=42,
            perplexity=perplexity,
            n_iter=300
        )
        try:
            tsne_results = tsne.fit_transform(tfidf_matrix.toarray())
        except Exception as e:
            return {
                "error": f"t-SNE 실패: {str(e)}",
                "topics": topics,
                "tsne_data": []
            }
    else:
        return {
            "error": "t-SNE를 수행하기에 데이터가 부족합니다",
            "topics": topics,
            "tsne_data": []
        }
    
    # t-SNE 결과와 토픽 정보 결합
    tsne_data = []
    for i, (x, y) in enumerate(tsne_results):
        tsne_data.append({
            "x": float(x),
            "y": float(y),
            "topic": int(doc_topics[i]),
            "rating": float(valid_reviews[i].get('rating', 0)),
            "preview": valid_reviews[i]['review_content'][:30] + "..."
        })
    
    return {
        "topics": topics,
        "tsne_data": tsne_data,
        "n_reviews": len(valid_reviews)
    }
