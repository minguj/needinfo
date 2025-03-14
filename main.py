import time
import pymysql
import schedule
import redis
from src.db import get_urls  # RDS에서 URL을 가져오는 함수
from src.crawler import get_final_url  # 크롤링 및 업데이트 함수
from src.crawler import update_final_url  # final_url을 업데이트하는 함수
from src.crawler import get_info
from src.crawler import update_info_place
from src.crawler import update_process
from src.crawler import update_error_status

from src.utils import get_corkage_text

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def descget():
    urls = get_urls()
    for url_info in urls:
        final_url = url_info['place_url']
        pid = url_info['id']

        try:
            print(f"준비된 url {pid} : {final_url}")
            info = get_info(final_url)
            if info['placeUrl']:
                print(f"placeUrl: {info['placeUrl']}")
                print(f"placeInfo: {info['placeInfo']}")
                print(f"placeDesc: {info['placeDesc']}")

                result = update_info_place(pid, info['placeUrl'], info['placeInfo'], info['placeDesc'])
                if result:
                    print(f"[O] ID {pid} 업데이트")
                else:
                    print(f"❌ ID {pid} 업데이트 실패")
        except Exception as e:
            print(f"상세정보 크롤링 실패: {e}")

def main():
    # 1. RDS에서 크롤링할 URL 가져오기
    urls = get_urls()
    
    if not urls:
        print("처리할 URL이 없습니다.")
        return
    
    # 2. 각 URL에 대해 크롤링을 진행하고 데이터 업데이트
    for url_info in urls:
        search_url = url_info['search_url']
        final_url = url_info['final_url']
        pid = url_info['pid']  # `pid`는 places 테이블의 row id
        
        # search_url이 빈 문자열인지 체크
        if search_url:     
            print(f"크롤링 시작: {search_url}")
            time.sleep(1)

            # 크롤링 및 final_url 생성
            try:
                final_url = get_final_url(search_url)
                if final_url:
                    print(f"생성된 final_url: {final_url}")
                    url_info['final_url'] = final_url  # url_info의 final_url을 업데이트
                    update_final_url(url_info['id'], final_url)  # needinfo 테이블에 업데이트
                else:
                    print(f"final_url 생성 실패: {search_url}")
            except Exception as e:
                print(f"크롤링 실패: {e}")
            time.sleep(2)  # 예시로 2초 대기
            
        if final_url:
            print(f"상세정보 크롤링 시작: {final_url}")

            try:
                info = get_info(final_url)
                if info['placeUrl']:
                    print(f"placeUrl: {info['placeUrl']}")
                    print(f"placeInfo: {info['placeInfo']}")
                    print(f"placeDesc: {info['placeDesc']}")
                    result = update_info_place(pid, info['placeUrl'], info['placeInfo'], info['placeDesc'])

                    if result:
                        print(f"✅ ID {pid} 업데이트 성공")
                        result = update_process(url_info['id'])
                        if result:
                            print(f"✅ NEEDINFO ID {url_info['id']} 업데이트 성공")
                        else:
                            print(f"❌ NEEDINFO ID {url_info['id']} 업데이트 실패")
                    else:
                        print(f"❌ ID {pid} 업데이트 실패")
                else:
                    # 여기에서 에러 코드 업데이트
                    print(f"❌ errormessage : {info['error_status']}")
                    result = update_error_status(url_info['id'], info['error_status'])
                    if result:
                        print(f"✅ NEEDINFO ID {url_info['id']} 에러정보 업데이트 성공")
                    else:
                        print(f"❌ NEEDINFO ID {url_info['id']} 에러정보 업데이트 실패")
                    print(f"❌ INFO_URL에서 크롤링 하지 못하여 {pid} 업데이트 실패")

            except Exception as e:
                print(f"상세정보 크롤링 실패: {e}")
    
# Redis 이벤트 리스너
def listen_for_events():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("new_url")  # Kotlin에서 발행할 채널

    print("📡 Redis 이벤트 리스너 대기 중...")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            print(f"🔔 새 이벤트 수신: {message['data']}")  # ✅ decode 제거
            main()  # main 실행

def gett():
    in_text = """
이맛은 고양이도 알지 의 베테카텐
    """
    get_corkage_text(in_text)

if __name__ == "__main__":
    # DB연동 테스트용
    #descget()

    # 텍스트파서만 테스트
    #gett()

    #main()
    
    # 원상복구는 리스너 작동,  그리고 db.py 쿼리문 복구
    listen_for_events()
