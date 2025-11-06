from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
from typing import Dict, List
import re

async def crawl_app_info(app_id: str) -> Dict:
    """Google Play Store에서 앱 정보를 크롤링합니다."""
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(15000)  # 15초 타임아웃
            
            url = f"https://play.google.com/store/apps/details?id={app_id}&hl=ko&gl=KR"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # 페이지 로딩 대기
            
            # 앱명 추출 (더 간단한 셀렉터 사용)
            app_name = ""
            try:
                app_name = await page.locator("h1 span").first.text_content(timeout=5000) or ""
            except:
                try:
                    app_name = await page.locator("h1").first.text_content(timeout=5000) or ""
                except:
                    pass
            
            if not app_name:
                raise Exception(f"앱을 찾을 수 없습니다. 앱 ID를 확인해주세요: {app_id}")
            
            # 리뷰수 추출
            review_count = "정보 없음"
            try:
                # 여러 가능한 셀렉터 시도
                selectors = [
                    "div.g1rdde",
                    "[aria-label*='리뷰']",
                    "div:has-text('리뷰')"
                ]
                for selector in selectors:
                    try:
                        text = await page.locator(selector).first.text_content(timeout=3000)
                        if text and any(char.isdigit() for char in text):
                            review_count = text.strip()
                            break
                    except:
                        continue
            except:
                pass
            
            # 별점 추출
            rating = "정보 없음"
            try:
                # 모든 role='img' 요소를 찾아서 별점 확인
                img_elements = await page.locator("div[role='img']").all()
                
                for element in img_elements:
                    try:
                        aria_label = await element.get_attribute("aria-label")
                        if aria_label and ("별" in aria_label or "star" in aria_label.lower()):
                            # "별표 5개 만점에 4.5개를 받았습니다" 형식
                            if "만점" in aria_label:
                                match = re.search(r'만점에\s*(\d+\.?\d*)', aria_label)
                                if match:
                                    rating = match.group(1)
                                    break
                            
                            # "4.5점" 형식
                            match = re.search(r'(\d+\.?\d*)\s*점', aria_label)
                            if match:
                                num = float(match.group(1))
                                if num <= 5:  # 별점은 5점 이하
                                    rating = match.group(1)
                                    break
                            
                            # 소수점 숫자만 있는 경우 (예: "4.5")
                            match = re.search(r'(\d+\.\d+)', aria_label)
                            if match:
                                num = float(match.group(1))
                                if num <= 5:
                                    rating = match.group(1)
                                    break
                    except:
                        continue
                    
            except Exception as e:
                pass
            
            # 다운로드수 추출
            download_count = "정보 없음"
            try:
                # 대체 셀렉터 (더 안정적)
                selectors = [
                    "div.JU1wdd > div > div > div:nth-child(2) > div.ClM7O",
                    "div.ClM7O",
                    "[aria-label*='다운로드']",
                    "div:has-text('다운로드')"
                ]
                
                for selector in selectors:
                    try:
                        text = await page.locator(selector).first.text_content(timeout=2000)
                        if text and any(char.isdigit() for char in text):
                            download_count = text.strip()
                            break
                    except:
                        continue
            except Exception as e:
                pass
            
            result = {
                "app_id": app_id,
                "app_name": app_name.strip(),
                "review_count": review_count,
                "download_count": download_count,
                "rating": rating
            }
            
            await browser.close()
            return result
            
    except PlaywrightTimeoutError:
        if browser:
            await browser.close()
        raise Exception(f"페이지 로딩 시간 초과. 네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.")
    except Exception as e:
        if browser:
            await browser.close()
        raise Exception(f"앱 정보 크롤링 실패: {str(e)}")

async def crawl_app_reviews(app_id: str, max_reviews: int = 10) -> List[Dict]:
    """Google Play Store에서 앱 리뷰를 크롤링합니다."""
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(15000)
            
            url = f"https://play.google.com/store/apps/details?id={app_id}&hl=ko&gl=KR&showAllReviews=true"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            reviews = []
            
            try:
                # 리뷰 섹션으로 스크롤
                try:
                    await page.locator("button:has-text('리뷰 모두 보기')").first.click(timeout=5000)
                    await asyncio.sleep(2)
                except:
                    # 버튼이 없으면 페이지에 이미 리뷰가 표시되어 있음
                    pass
                
                # 리뷰 항목들 추출
                review_items = await page.locator("div.RHo1pe").all()
                
                if not review_items:
                    # 다른 셀렉터 시도
                    review_items = await page.locator("[class*='review']").all()
                
                for idx, review_item in enumerate(review_items[:max_reviews]):
                    try:
                        # 별점 추출
                        rating = 5.0  # 기본값
                        try:
                            rating_element = await review_item.locator("div[role='img']").first.get_attribute("aria-label", timeout=2000)
                            if rating_element:
                                match = re.search(r'(\d+)점', rating_element)
                                if match:
                                    rating = float(match.group(1))
                        except:
                            pass
                        
                        # 리뷰 내용 추출
                        review_content = ""
                        try:
                            review_content = await review_item.locator("div.h3YV2d").first.text_content(timeout=2000) or ""
                        except:
                            try:
                                review_content = await review_item.locator("[class*='content']").first.text_content(timeout=2000) or ""
                            except:
                                pass
                        
                        # 리뷰 작성일 추출
                        review_date = "날짜 정보 없음"
                        try:
                            review_date = await review_item.locator("span.bp9Aid").first.text_content(timeout=2000) or "날짜 정보 없음"
                        except:
                            pass
                        
                        if review_content:  # 리뷰 내용이 있는 경우만 추가
                            reviews.append({
                                "rating": rating,
                                "review_content": review_content.strip(),
                                "review_date": review_date.strip()
                            })
                        
                    except Exception as e:
                        print(f"리뷰 {idx} 추출 중 오류 (건너뜀): {str(e)}")
                        continue
                
                await browser.close()
                
                if not reviews:
                    raise Exception("리뷰를 찾을 수 없습니다. 이 앱에는 리뷰가 없거나 접근할 수 없습니다.")
                
                return reviews
                
            except Exception as e:
                await browser.close()
                raise Exception(f"리뷰 크롤링 실패: {str(e)}")
                
    except PlaywrightTimeoutError:
        if browser:
            await browser.close()
        raise Exception(f"리뷰 페이지 로딩 시간 초과. 네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.")
    except Exception as e:
        if browser:
            await browser.close()
        if "리뷰 크롤링 실패" in str(e):
            raise
        raise Exception(f"리뷰 크롤링 중 오류 발생: {str(e)}")
