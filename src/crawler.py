import requests
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from faker import Faker
import re
from src.db import get_connection  # 데이터베이스 연결을 위한 함수 (나중에 작성)
from src.utils import extract_corkage_info

# 랜덤 User-Agent, Referer, Accept-Language 설정
def generate_random_headers():
    faker = Faker()

    # 랜덤 User-Agent
    user_agent = faker.user_agent()

    # 더 그럴싸한 랜덤 Referer 설정
    # referers = [
    #     "https://www.google.com/search?q=" + faker.word(),
    #     "https://www.bing.com/search?q=" + faker.word(),
    #     "https://www.yahoo.com/search?p=" + faker.word(),
    #     "https://www.naver.com/search?query=" + faker.word(),
    #     "https://www.youtube.com/watch?v=" + faker.sha1()[:10],  # 유튜브 비디오 URL
    #     "https://www.reddit.com/r/" + random.choice(["technology", "python", "webdev"]) + "/",
    #     "https://www.instagram.com/p/" + faker.sha1()[:10] + "/",
    #     "https://www.twitter.com/" + random.choice(["elonmusk", "python_dev", "techcrunch"]) + "/",
    #     "https://www.facebook.com/" + faker.user_name() + "/",
    # ]

    # referer = random.choice(referers)

    # 랜덤 Accept-Language (언어 설정)
    accept_language = random.choice(["en-US,en;q=0.9", "ko-KR,ko;q=0.9"])

    return {
        "User-Agent": user_agent,
        #"Referer": referer,
        "Accept-Language": accept_language
    }

def update_info_place(pid, place_url, place_info, place_desc):
    # placeDesc를 콤마로 구분하여 하나의 문자열로 결합
    place_desc_str = ",".join(place_desc) if place_desc else ""
    place_info_str = ",".join(place_info) if place_info else ""

    # ✅ 콜키지 가능 여부 확인
    keywords = ["콜키지", "corkage", "병입료", "주류반입"]
    no_keywords = ["주류반입 금지", "주류반입금지"]
    
    is_corkage_available = any(keyword in place_desc_str for keyword in keywords) and not any(no_keyword in place_desc_str for no_keyword in no_keywords)
    is_corkage_available = is_corkage_available or "콜키지 가능" in place_info

    # ✅ 무료 콜키지 여부 확인
    free_keywords = ["콜키지 무료", "콜키지무료", "콜키지프리", "콜키지 프리", "무료", "프리"]
    is_free_corkage = any(keyword in place_desc_str for keyword in free_keywords)
    is_free_corkage = is_free_corkage or "무료" in place_info

    # places 테이블에 업데이트할 SQL 쿼리
    update_query = """
    UPDATE places
    SET 
        corkage_available = %s,
        free_corkage = %s,
        place_info = %s,
        place_url = %s,
        corkage_infolist = %s
    WHERE id = %s;
    """

    # DB 연결 (PostgreSQL 예시)
    try:
        # DB 연결 설정 (적절한 DB 연결 정보로 수정)
        conn = get_connection()
        cursor = conn.cursor()

        # 실행할 값 준비
        cursor.execute(update_query, (
            is_corkage_available,
            is_free_corkage,
            place_info_str,
            place_url,
            place_desc_str,
            pid
        ))

        # 변경사항 커밋
        conn.commit()
        return True

    except Exception as e:
        print(f"DB 업데이트 실패: {e}")
        return False
    finally:
        if conn:
            cursor.close()
            conn.close()


def get_info(final_url):
    info_val = {}
    info_val['placeUrl'] = final_url
    info_val['error_status'] = None  # 에러 상태 초기화
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        page = context.new_page()
        page.evaluate("() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }) }")
        try:
            print(f"상세정보 크롤링 시작: {final_url}")
            page.goto(final_url, timeout=10000)
            page.wait_for_load_state("networkidle")
            
            # 페이지가 로드된 후, URL을 확인하여 'information' 탭으로 리디렉션되었는지 확인
            if "information" not in page.url:
                info_val['error_status'] = 'not_information_tab'
                info_val['placeUrl'] = None
                print(f"페이지가 'information' 탭으로 리디렉션되지 않았습니다. 현재 URL: {page.url}")
                return info_val
            
            # 429 Too Many Requests 처리
            if "too many requests" in page.content().lower() or '과도한 접근 요청으로' in page.content():
                info_val['error_status'] = 'too_many_requests'
                info_val['placeUrl'] = None
                print("Too Many Requests 오류 발생 (429). 페이지 로드 실패.")
                return info_val
            
            # 페이지 로딩 대기
            page.wait_for_load_state("networkidle")
            print("페이지 로딩 완료!")
            time.sleep(2)
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            
            # placeInfo 찾기
            try:
                place_info_elements = page.locator("div.woHEA ul.JU0iX li.c7TR6 div, div.woHEA ul.JU0iX li.c7TR6 span").all()
                place_info = [item.inner_text().strip() for item in place_info_elements if item.inner_text().strip()]
                if not place_info:
                    info_val['error_status'] = 'place_info_missing'
                    print("placeInfo 요소가 로드되지 않았습니다.")
            except Exception:
                place_info = []
                info_val['error_status'] = 'place_info_missing'
                print("placeInfo 요소를 찾을 수 없습니다.")
            
            # placeDesc 찾기
            try:
                place_desc_elements = page.locator("div.T8RFa.CEyr5").all()
                place_desc = "\n".join([desc.inner_text().strip() for desc in place_desc_elements if desc.inner_text().strip()])
                if not place_desc:
                    info_val['error_status'] = 'place_desc_missing'
                    print("placeDesc 요소가 로드되지 않았습니다.")
            except Exception:
                place_desc = ""
                info_val['error_status'] = 'place_desc_missing'
                print("placeDesc 요소를 찾을 수 없습니다.")
            
            # placeDesc가 없으면 다른 div.T8RFa를 찾아보기
            if not place_desc:
                try:
                    place_desc_elements = page.locator("div.T8RFa").all()
                    place_desc = "\n".join([desc.inner_text().strip() for desc in place_desc_elements if desc.inner_text().strip()])
                except Exception:
                    info_val['error_status'] = 'place_desc_missing'
                    print("다른 placeDesc 요소를 찾을 수 없습니다.")
            
            # 결과 저장
            print(f"INFO_VAL[] 저장전 : {place_info} ")
            info_val['placeInfo'] = place_info
            info_val['placeDesc'] = extract_corkage_info(place_desc) if place_desc else ""
            print(f"INFO_VAL[] 저장후 : {info_val} ")
            
        except Exception as e:
            info_val['placeUrl'] = None
            info_val['error_status'] = 'general_error'
            print(f"크롤링 실패: {e}")
            print("에러가 발생한 URL:", final_url)
        
        finally:
            browser.close()
    
    return info_val


def get_final_url(search_url):
    options = webdriver.ChromeOptions()
    # 랜덤 헤더 설정
    headers = generate_random_headers()
    for key, value in headers.items():
        options.add_argument(f'{key}={value}')
    #options.add_argument(f"user-agent={random_user_agent}")  # 랜덤 User-Agent 사용
    #options.add_argument("--incognito")
    options.add_argument("--headless")  # 브라우저 창을 띄우지 않고 백그라운드에서 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")  # GPU 사용을 비활성화
    options.add_argument("--disable-dev-shm-usage")  # 메모리 관련 오류 방지
    options.add_argument("--disable-software-rasterizer")  # 소프트웨어 렌더링 비활성화

    # WebDriver 초기화
    driver = webdriver.Chrome(options=options)


    final_url = None  # 미리 선언

    try:
        # Selenium을 사용하여 페이지 열기
        driver.get(search_url)

        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div#_title a")),
                EC.visibility_of_element_located((By.CSS_SELECTOR, "a.ApCpt.k4f_J")),
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.CHC5F a.tzwk0")),
            )
        )
        time.sleep(2)
        place_id = None  # place_id 초기화

        # ✅ 첫 번째 요소 찾기 (a.ApCpt.k4f_J)
        try:
            place_link_element = driver.find_element(By.CSS_SELECTOR, "a.ApCpt.k4f_J")
            place_link = place_link_element.get_attribute('href')

            match = re.search(r"/place/(\d+)", place_link)
            if match:
                place_id = match.group(1)

        except NoSuchElementException:
            print("요소 `a.ApCpt.k4f_J`를 찾을 수 없습니다.")

        # ✅ 두 번째 요소 찾기 (div#_title a)
        if not place_id:  # 첫 번째 시도 실패하면 두 번째 시도
            try:
                place_link_element = driver.find_element(By.CSS_SELECTOR, "div#_title a")
                place_link = place_link_element.get_attribute('href')

                match = re.search(r"/restaurant/(\d+)", place_link)
                if match:
                    place_id = match.group(1)

            except NoSuchElementException:
                print("요소 `div#_title a`를 찾을 수 없습니다.")

        # ✅ 세 번째 요소 찾기 (div.CHC5F a.tzwk0)
        if not place_id:  # 두 번째 시도 실패하면 세 번째 시도
            try:
                place_link_element = driver.find_element(By.CSS_SELECTOR, "div.CHC5F a.tzwk0")
                place_link = place_link_element.get_attribute('href')

                match = re.search(r"/restaurant/(\d+)", place_link)
                if match:
                    place_id = match.group(1)

            except NoSuchElementException:
                print("요소 `div.CHC5F a.tzwk0`를 찾을 수 없습니다.")                

        # ✅ place_id가 있다면 final_url 생성
        if place_id:
            final_url = f"https://m.place.naver.com/restaurant/{place_id}/information"
        else:
            print("⚠ placeId를 찾을 수 없습니다.")

    except TimeoutException:
        print("⏳ 페이지 로딩이 시간 초과되었습니다.")
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")

    finally:
        # WebDriver 종료
        driver.quit()

    return final_url

def update_final_url(id, final_url):
    """ id에 맞는 needinfo 테이블 row에서 final_url을 업데이트하는 함수 """
    try:
        # DB 연결
        conn = get_connection()
        cursor = conn.cursor()

        # SQL 업데이트 쿼리 작성
        update_query = """
        UPDATE needinfo
        SET final_url = %s, search_url = ""
        WHERE id = %s
        """
        
        # 쿼리 실행
        cursor.execute(update_query, (final_url, id))
        
        # 변경사항 커밋
        conn.commit()
        
        print(f"final_url 업데이트 완료: id = {id}, final_url = {final_url}")
        
    except Exception as e:
        print(f"final_url 업데이트 실패: {e}")
    
    finally:
        # 연결 종료
        cursor.close()
        conn.close()

def update_process(id):
    """ needinfo 테이블에서 특정 ID의 process 값을 1로 업데이트하는 함수 """
    try:
        # DB 연결
        conn = get_connection()
        cursor = conn.cursor()

        # SQL 업데이트 쿼리 작성
        update_query = """
        UPDATE needinfo
        SET process = 1
        WHERE id = %s
        """
        
        # 쿼리 실행
        cursor.execute(update_query, (id,))
        
        # 변경사항 커밋
        conn.commit()
        
        print(f"✅ needinfo 테이블 업데이트 완료: id = {id}, process = 1")
        
        return True  # 성공

    except Exception as e:
        print(f"❌ needinfo 테이블 업데이트 실패: {e}")
        return False  # 실패
    
    finally:
        # 연결 종료
        cursor.close()
        conn.close()

def update_error_status(id, error_status):
    """ needinfo 테이블에서 특정 ID의 error_status 값을 업데이트하는 함수 """
    try:
        # DB 연결
        conn = get_connection()
        cursor = conn.cursor()

        # 업데이트 쿼리 초기화
        update_query = """
        UPDATE needinfo
        SET error_status = %s
        WHERE id = %s
        """

        # 'not_information_tab'인 경우 process = 9 설정
        if error_status == 'not_information_tab':
            update_query = """
            UPDATE needinfo
            SET error_status = %s, process = 9
            WHERE id = %s
            """
        
        # 쿼리 실행
        cursor.execute(update_query, (error_status,id))
        print(f"⏩ 업데이트된 행의 수: {cursor.rowcount}")
        
        # 변경사항 커밋
        conn.commit()
        
        print(f"✅ needinfo 테이블 에러갱신 완료: id = {id}, error = {error_status}")
        
        return True  # 성공

    except Exception as e:
        print(f"❌ needinfo 테이블 에러갱신 실패: {e}")
        return False  # 실패
    
    finally:
        # 연결 종료
        cursor.close()
        conn.close()