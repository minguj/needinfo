import re

def extract_corkage_info(input_text: str) -> list:
    corkage_pattern = re.compile(r".*(콜키지.?프리|콜키지.?차지|콜키지|corkage|병입료|주류반입|와인|메그넘|위스키|사케).*", re.IGNORECASE)

    return [line.strip() for line in input_text.split('\n') if line.strip() and corkage_pattern.match(line)]
