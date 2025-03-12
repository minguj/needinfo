import redis
import json
from main import main  # 기존 크롤링 코드 import

def redis_listener():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("new_url")  # ✅ "new_url" 채널 구독

    print("📡 Redis 이벤트 대기 중...")

    for message in pubsub.listen():
        if message["type"] == "message":
            print(f"📩 새로운 URL 이벤트 수신: {message['data']}")
            main()  # ✅ 기존 크롤링 로직 실행

if __name__ == "__main__":
    redis_listener()
