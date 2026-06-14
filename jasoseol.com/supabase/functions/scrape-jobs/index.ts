import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const BASE_URL = "https://jasoseol.com";
const SEARCH_URL = "https://jasoseol.com/search";
const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
  "Accept-Language": "ko-KR,ko;q=0.9",
};

// 자소설닷컴 대분류 직무 ID → 이름 매핑
const DUTY_LARGE: Record<number, string> = {
  91: "경영·사무",
  92: "마케팅·광고·홍보",
  93: "무역·유통",
  94: "IT·인터넷",
  95: "생산·제조",
  96: "영업·고객상담",
  97: "건설",
  98: "금융",
  99: "연구개발·설계",
  100: "디자인",
  101: "미디어",
  102: "전문·특수직",
};

interface RawJob {
  id: number;
  name: string;
  title: string;
  start_time: string | null;
  end_time: string | null;
  employments: Array<{
    duty_group_ids: number[];
    division: number[];
  }>;
  company_group: {
    business_type: string | null;
  } | null;
}

const BUSINESS_TYPE_MAP: Record<string, string> = {
  large_enterprise: "대기업",
  medium_enterprise: "중견기업",
  small_enterprise: "중소기업",
  public_institution: "공공기관",
  foreign_enterprise: "외국계",
  startup: "스타트업",
};

const DIVISION_MAP: Record<number, string> = {
  1: "신입",
  2: "경력",
  3: "신입, 경력",
  4: "인턴",
  5: "계약직",
};

function parseNextData(html: string): { jobs: RawJob[]; hasNext: boolean } {
  const match = html.match(
    /<script id="__NEXT_DATA__" type="application\/json">(.*?)<\/script>/
  );
  if (!match) return { jobs: [], hasNext: false };

  const data = JSON.parse(match[1]);
  const queries = data?.props?.pageProps?.dehydratedState?.queries ?? [];
  const jobQuery = queries.find((q: { queryKey: string[] }) =>
    q.queryKey?.[0] === "jobSearch"
  );
  const items: RawJob[] = jobQuery?.state?.data?.data ?? [];

  // 다음 페이지 여부: 현재 페이지 * 20 < total_count
  const totalCount: number = jobQuery?.state?.data?.totalCount ?? 0;
  const currentPage: number =
    jobQuery?.queryKey?.[1]?.page ?? 1;
  const hasNext = currentPage * 20 < totalCount;

  return { jobs: items, hasNext };
}

function toDbRow(job: RawJob, scrapedAt: string) {
  // duty_group_ids 전체에서 대분류(91~102)만 추출
  const allDutyIds = job.employments.flatMap((e) => e.duty_group_ids ?? []);
  const largeDutyIds = [...new Set(allDutyIds.filter((id) => id in DUTY_LARGE))];

  // 채용 형태: division 값에서 변환
  const divisions = [...new Set(job.employments.flatMap((e) => e.division ?? []))];
  const employmentType = divisions
    .map((d) => DIVISION_MAP[d])
    .filter(Boolean)
    .join(", ") || null;

  const companyType =
    BUSINESS_TYPE_MAP[job.company_group?.business_type ?? ""] ?? null;

  return {
    recruit_id: String(job.id),
    url: `${BASE_URL}/recruit/${job.id}`,
    company_name: job.name ?? null,
    job_title: job.title ?? null,
    company_type: companyType,
    employment_type: employmentType,
    start_date: job.start_time ?? null,
    end_date: job.end_time ?? null,
    duty_group_ids: largeDutyIds,
    scraped_at: scrapedAt,
  };
}

async function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  let page = 1;
  let total = 0;
  const scrapedAt = new Date().toISOString();

  try {
    while (true) {
      const url = page === 1 ? SEARCH_URL : `${SEARCH_URL}?page=${page}`;
      console.log(`페이지 ${page} 수집 중...`);

      const resp = await fetch(url, { headers: HEADERS });
      if (!resp.ok) {
        console.error(`요청 실패: HTTP ${resp.status}`);
        break;
      }

      const html = await resp.text();
      const { jobs: rawJobs, hasNext } = parseNextData(html);

      if (rawJobs.length === 0) {
        console.log("공고 없음 — 종료");
        break;
      }

      const rows = rawJobs.map((j) => toDbRow(j, scrapedAt));

      const { error } = await supabase
        .from("job_listings")
        .upsert(rows, { onConflict: "recruit_id" });

      if (error) {
        console.error("DB 저장 실패:", error.message);
        break;
      }

      total += rows.length;
      console.log(`  ${rows.length}건 저장 (누적 ${total}건)`);

      if (!hasNext) break;
      page++;
      await delay(1000);
    }

    return Response.json({ success: true, total });
  } catch (e) {
    console.error(e);
    return Response.json({ success: false, error: String(e) }, { status: 500 });
  }
});
