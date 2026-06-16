import json
import os
import re
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://jasoseol.com"
SEARCH_URL = "https://jasoseol.com/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 소분류 ID → 대분류 ID 매핑 (jasoseol.com duties 구조 기반)
SMALL_TO_LARGE = {
    103:91,104:91,105:91,106:91,107:91,108:91,109:91,110:91,111:91,112:91,113:91,114:91,
    115:91,116:91,117:91,118:91,119:91,120:91,121:91,122:91,123:91,124:91,125:91,126:91,
    127:91,128:91,129:91,130:91,131:91,
    132:92,133:92,134:92,135:92,136:92,137:92,138:92,139:92,140:92,141:92,142:92,143:92,144:92,
    145:93,146:93,147:93,148:93,149:93,150:93,151:93,152:93,153:93,154:93,155:93,156:93,157:93,158:93,159:93,
    160:94,161:94,162:94,163:94,164:94,165:94,166:94,167:94,168:94,169:94,170:94,171:94,172:94,173:94,174:94,175:94,176:94,177:94,178:94,179:94,180:94,181:94,182:94,
    183:95,184:95,185:95,186:95,187:95,188:95,189:95,190:95,191:95,192:95,193:95,
    194:96,195:96,196:96,197:96,198:96,199:96,200:96,201:96,
    202:97,203:97,204:97,205:97,206:97,207:97,208:97,209:97,
    210:98,211:98,212:98,213:98,214:98,215:98,
    216:99,217:99,218:99,219:99,220:99,221:99,222:99,223:99,224:99,225:99,226:99,227:99,228:99,229:99,230:99,231:99,232:99,233:99,234:99,235:99,236:99,
    237:100,238:100,239:100,240:100,241:100,242:100,243:100,244:100,245:100,246:100,
    247:101,248:101,249:101,250:101,251:101,252:101,
    253:102,254:102,255:102,256:102,257:102,258:102,259:102,260:102,261:102,262:102,263:102,264:102,
}

BUSINESS_TYPE_MAP = {
    "large_enterprise": "대기업",
    "medium_enterprise": "중견기업",
    "small_enterprise": "중소기업",
    "public_institution": "공공기관",
    "foreign_enterprise": "외국계",
    "startup": "스타트업",
}

DIVISION_MAP = {
    1: "신입",
    2: "경력",
    3: "신입, 경력",
    4: "인턴",
    5: "계약직",
}


def parse_next_data(html: str) -> tuple[list[dict], bool]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not match:
        return [], False

    data = json.loads(match.group(1))
    queries = data.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
    job_query = next((q for q in queries if q.get("queryKey", [None])[0] == "jobSearch"), None)
    if not job_query:
        return [], False

    items = job_query.get("state", {}).get("data", {}).get("data", [])
    total_count = job_query.get("state", {}).get("data", {}).get("totalCount", 0)
    current_page = job_query.get("queryKey", [None, {}])[1].get("page", 1) if len(job_query.get("queryKey", [])) > 1 else 1
    has_next = current_page * 20 < total_count

    return items, has_next


def to_db_row(job: dict, scraped_at: str) -> dict:
    employments = job.get("employments", [])
    all_duty_ids = [d for e in employments for d in (e.get("duty_group_ids") or [])]
    large_duty_ids = list({SMALL_TO_LARGE[d] for d in all_duty_ids if d in SMALL_TO_LARGE})

    divisions = list({d for e in employments for d in (e.get("division") or [])})
    employment_type = ", ".join(filter(None, [DIVISION_MAP.get(d) for d in sorted(divisions)])) or None

    business_type = (job.get("company_group") or {}).get("business_type")
    company_type = BUSINESS_TYPE_MAP.get(business_type) if business_type else None

    return {
        "source": "jasoseol",
        "source_job_id": str(job["id"]),
        "url": f"{BASE_URL}/recruit/{job['id']}",
        "company_name": job.get("name"),
        "title": job.get("title"),
        "company_type": company_type,
        "employment_type": employment_type,
        "start_date": job.get("start_time"),
        "end_date": job.get("end_time"),
        "duty_group_ids": large_duty_ids,
        "scraped_at": scraped_at,
    }


def save_to_supabase(rows: list[dict]):
    if not rows:
        return
    for attempt in range(3):
        try:
            supabase.table("unified_job_listings").upsert(rows, on_conflict="source,source_job_id").execute()
            print(f"  저장 완료: {len(rows)}건")
            return
        except Exception as e:
            print(f"  저장 재시도 {attempt+1}/3: {e}")
            time.sleep(3 * (attempt + 1))
    print(f"  저장 실패 — 건너뜀")


def scrape_all():
    page = 1
    total = 0
    scraped_at = datetime.utcnow().isoformat() + "Z"

    while True:
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
        print(f"페이지 {page} 수집 중... ({url})")

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                break
            except Exception as e:
                print(f"  재시도 {attempt+1}/3: {e}")
                time.sleep(3 * (attempt + 1))
        else:
            print("요청 실패 — 종료")
            break
        if resp.status_code != 200:
            print(f"요청 실패: HTTP {resp.status_code}")
            if resp.status_code in (502, 503):
                time.sleep(10)
                continue
            break

        items, has_next = parse_next_data(resp.text)
        if not items:
            print("공고 없음 — 종료")
            break

        rows = [to_db_row(job, scraped_at) for job in items]
        total += len(rows)
        print(f"  {len(rows)}건 파싱 (누적 {total}건)")
        save_to_supabase(rows)

        if not has_next:
            break

        page += 1
        time.sleep(1)

    print(f"\n완료: 총 {total}건 수집")


if __name__ == "__main__":
    scrape_all()
