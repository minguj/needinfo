import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# RDS 연결 함수
def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor
    )

# URL을 가져오는 함수 (이전에 작성한 부분)
def get_urls():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, pid, search_url, final_url FROM needinfo WHERE process = 0"
            #sql = "SELECT id, pid, search_url, final_url FROM needinfo WHERE process = FALSE LIMIT 1"
            cursor.execute(sql)
            result = cursor.fetchall()
            return result
    finally:
        conn.close()
