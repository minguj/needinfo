import re
import json

def merge_unique_sentences(summary, original_sentences):
    seen_sentences = set()
    ordered_sentences = []

    for sentence in original_sentences:  # 원래 문장 리스트 순서 유지
        for key, value in summary.items():
            if isinstance(value, list) and sentence in value:
                if sentence not in seen_sentences:  # 중복 확인
                    seen_sentences.add(sentence)
                    ordered_sentences.append(sentence)

    return "\n".join(ordered_sentences)  # 순서를 유지하며 문자열로 병합

def extract_corkage_info(input_text: str) -> list:
    corkage_pattern = re.compile(r".*(콜키지.?프리|콜키지.?차지|콜키지|corkage|병입료|주류반입|와인|메그넘|위스키|사케|샴페인).*", re.IGNORECASE)

    return [line.strip() for line in input_text.split('\n') if line.strip() and corkage_pattern.match(line)]

def merge_liquor_types(text: str) -> str:
    text = re.sub(r"와인\s*콜키즈", "와인 콜키지", text, flags=re.IGNORECASE)
    text = re.sub(r"위스키\s*콜키즈", "위스키 콜키지", text, flags=re.IGNORECASE)
    """
    주종이 연속적으로 등장하는 경우 하나의 단어로 합침
    예: "와인 샴페인 위스키" → "와인_샴페인_위스키"
    """

    liquor_types = ["기타 주류", "고량주", "잇쇼빙", "니혼슈", "증류주", "양주", "전통주", "와인", "샴페인", "위스키", "사케", "스파클링", "화이트", "레드"]

    # 🔹 쉼표 & 공백을 포함하여 연속적인 주종 그룹 찾기
    pattern = r"(" + "|".join(liquor_types) + r")(?:[\s,]+(" + "|".join(liquor_types) + r"))+"

    def merge_match(match):
        """정규식으로 찾은 그룹을 '_'로 병합"""
        group = re.findall(r"\b(" + "|".join(liquor_types) + r")\b", match.group(0))
        return "_".join(group)

    return re.sub(pattern, merge_match, text)

def clean_unmatched_parentheses(text: str) -> str:
    """괄호 짝이 맞지 않는 경우 괄호 제거"""
    while text.count("(") != text.count(")"):
        text = re.sub(r"\(|\)", "", text, 1)  # 괄호 하나씩 제거
    return text.strip()

def get_corkage_text(input_text: str) -> str:
    print(f"\n[DEBUG] 원본 입력: {repr(input_text)}\n")  

    cleaned_text = merge_liquor_types(input_text)

    # 🔹 주종 단어 병합 적용
    cleaned_text = merge_liquor_types(cleaned_text)
    print(f"\n[DEBUG] 주종 병합 확인: {repr(cleaned_text)}\n")  

    # 🔹 숫자 콤마 처리
    cleaned_text = re.sub(r"(\d),(\d)", r"\1\2", cleaned_text)  
    cleaned_text = re.sub(r",", ".", cleaned_text)  

    # ✅ 콜키지 무료 패턴
    free_patterns = [
        r"\b콜키지\s*무료\b", r"\b콜키지\s*프리\b", r"\bCORKAGE\s*FREE\b",
        r"\bno\s*corkage\b", r"\b1\s*bottle\s*free\b",
        r"(\d+)\s*병\s*프리",
        r"(\d+)병\s*프리",
        r"(와인|위스키|사케|전통주|양주).*?반입"
    ]

    paid_patterns = [
        r"콜키지\s*(비용|유료|차지|fee|charge)", 
        r"\d+\s*(원|KRW|₩)", 
        r"\d+\s*만\s*원",  # ✅ "4만 원" 같은 표현 추가
        r"1인당",  
        r"(\d+)\s*(원|KRW|₩)",  
        r"(\d+)\s*만\s*원",  # ✅ 중복 방지를 위해 추가
        r"(\d+)\s*만?\s*원"
    ]

    # ✅ 특정 주종 불가 패턴 추가
    not_allowed_patterns = [
        r"(레드와인|red wine)\s*:\s*불가"
    ]

    # ✅ "테이블당 X병" 패턴
    per_table_patterns = [
        r"테이블\s*당\s*(\w+)?\s*\d+\s*병",
        r"테이블당\s*(\w+)?\s*\d+\s*병",
        r"per\s*table\s*\d+\s*bottles?",

        # 반입/소지/지참 관련 제한 없음 패턴
        r"(반입|소지|지참)\s*(가능한\s*)?병\s*(수)?\s*(에\s*)?(대한\s*)?(제한\s*(이\s*)?(없(음|습니다|어요|으니|다)|무제한|프리))",
        r"(반입|소지|지참)\s*(가능한\s*)?병\s*(수는)?\s*제한이\s*없(습니다|어요|으니|다)?",
        r"병\s*(반입|소지|지참)\s*가능\s*(수량)?\s*(제한\s*(없음|무제한))?",

        # 🔹 '인당 XX만원' 패턴
        r"인당\s*\d+\s*(만원|천원)\s*(추가)?",

        # 🔹 '무제한' 단독 패턴
        r"무제한"
    ]

    # ✅ 와인잔 & 오프너 패턴 추가
    glass_patterns = [r"디켄터", r"디캔터", r"와인잔", r"wine\s*glass", r"오프너", r"opener", r"글라스", r"broken", r"charge", r"브로큰", r"차지"]

    # ✅ 가격 패턴 (복합 주종 포함)
    price_patterns = {
        "wine": r"(화이트와인|샴페인|와인|red wine|메그넘(?:사이즈)?)(?:\s*\([^)]*\))?[_\s,:]*(\d{1,3}[,.]?\d{0,3}|\d+\s*만\s*원)\s*(원|KRW|₩)?",
        "whisky": r"(위스키|whisky|고도수|고용량)[^\d]*(\d{1,3}[,.]?\d{0,3}|\d+\s*만\s*원)\s*(원|KRW|₩)?",
        "sake": r"(니혼슈|사케|sake|시고빙|잇쇼빙)(?:\s*\([^)]*\))?[_\s,:]*(\d{1,3}[,.]?\d{0,3}|\d+\s*만\s*원)\s*(원|KRW|₩)?",
        "general": r"(증류주)[_\s,:]*(\d{1,3}[,.]?\d{0,3}|\d+\s*만\s*원)\s*(원|KRW|₩)?"
    }

    # ✅ "예약 및 문의" 문구 필터링 패턴 추가
    exclude_patterns = [
        r"예약\s*및\s*문의[:\s]*\d{2,3}-\d{3,4}-\d{4}"
    ]

    # 문장 단위 분리
    sentences = re.findall(r"[^.!?\n]+(?:\([^)]*\))*[^.!?\n]*[.!?]?", cleaned_text)
    sentences = [clean_unmatched_parentheses(sentence.strip(" ,*")) for sentence in sentences if sentence.strip()]

    print(f"[DEBUG] 문장 리스트:\n{json.dumps(sentences, ensure_ascii=False, indent=4)}\n")  

    results = []
    corkage_free_group = []
    corkage_paid_group = []
    corkage_not_allowed_group = []
    glass_table_group = []
    per_table_group = []
    last_free_idx = -1

    for idx, sentence in enumerate(sentences):
        print(f"[DEBUG] 검사 중 문장: {sentence}")  

        if not sentence or any(re.search(pattern, sentence, re.IGNORECASE) for pattern in exclude_patterns):
            continue  # 🔥 "예약 및 문의" 문장 제외

        if "콜키지" in sentence or "corkage" in sentence:
            corkage_free_group.append(sentence)

        is_free = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in free_patterns)


        is_paid = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in paid_patterns)
        is_per_table = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in per_table_patterns)
        is_not_allowed = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in not_allowed_patterns)
        has_glass = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in glass_patterns)

        if is_per_table:
            print(f"  → [MATCH] 'per_table' 감지됨: {sentence}")  
            per_table_group.append(sentence)

        price_info = {key: bool(re.search(pattern, sentence, re.IGNORECASE)) for key, pattern in price_patterns.items()}
        has_price = any(price_info.values())

        if is_free:
            print(f"  → [MATCH] 'is_free' 감지됨: {sentence}")  
            corkage_free_group.append(sentence)
            last_free_idx = idx
        elif last_free_idx != -1 and (idx - last_free_idx == 1):
            corkage_free_group.append(sentence)

        if is_paid or has_price:
            print(f"  → [MATCH] 'corkage_paid' 감지됨: {sentence}")  # 디버깅 출력 추가
            corkage_paid_group.append(sentence)

        if is_not_allowed:
            corkage_not_allowed_group.append(sentence)  

        if has_glass:
            glass_table_group.append(sentence)  

        results.append({
            "sentence": sentence,
            "corkage_free": is_free,
            "corkage_paid": is_paid,
            "per_table": is_per_table,
            "corkage_not_allowed": is_not_allowed,
            "has_glass": has_glass,
            **price_info
        })

    summary = {
        "corkage_free": corkage_free_group,
        "corkage_paid": corkage_paid_group,
        "corkage_not_allowed": corkage_not_allowed_group,  
        "glass_table": list(set(glass_table_group)),  
        "per_table": per_table_group,
        "prices": {
            "wine": [r["sentence"] for r in results if r["wine"]],
            "whisky": [r["sentence"] for r in results if r["whisky"]],
            "sake": [r["sentence"] for r in results if r["sake"]],  # ✅ 사케 가격 정보 추가
            "general": [
                r["sentence"] for r in results if r["general"]
                and not any(re.search(pattern, r["sentence"], re.IGNORECASE) for pattern in exclude_patterns)
            ]
        }
    }

    print(json.dumps(summary, ensure_ascii=False, indent=4))  
    
    merged_string = merge_unique_sentences(summary, sentences)
    print(merged_string)

    return merged_string