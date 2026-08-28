import type { AeoAcademyProfile, AeoArticle, AeoFaqItem, NaverBlogArticle } from "./types";

const AEO_SYSTEM_PROMPT = `당신은 오프라인 실용음악학원을 위한 SEO/AEO(Answer Engine Optimization) 전문 카피라이터입니다.
생성형 AI(ChatGPT, Gemini, Perplexity 등)가 인용·추천하기 쉬운 사실 기반 블로그 글로 재구성합니다.
이 버전은 티스토리·마크다운 발행을 전제로 합니다.

반드시 지킬 규칙:
1. 형용사적이고 모호한 표현("노래 잘 가르치는", "친절한", "최고의")은 제거하거나 최소화한다.
2. [학원 고유명사], [정확한 위치/지하철역], [명확한 수치/근거 데이터]를 문맥에 매끄럽게 포함한다.
3. 학원명·서비스명은 스펠링/명칭을 바꾸지 말고 단일 명칭으로 일관 유지한다.
4. 제목과 첫 단락은 "이 글의 핵심 주제가 무엇인가?"에 1문장으로 답할 수 있는 결론 중심 구조로 쓴다.
5. Markdown만 사용한다. 이모지·과도한 수식어·과장 광고 문구는 금지한다.
6. 원문에 없는 허위 수치·자격·성과를 지어내지 않는다. 제공된 근거 데이터만 사용한다.
7. 현장(학원·상담)에서 실제로 쓰는 말투를 유지한다. cent, Hz, dB 같은 장비 용어는 학부모·수강생이 이해하는 말로 바꾼다.
8. 수강생 실명·개인정보는 절대 넣지 않는다. "수강생", "입시 준비생" 등으로만 쓴다.
9. markdownBody에는 H1(#)과 FAQ 섹션을 넣지 않는다. 제목은 title, FAQ는 faq 필드로만 둔다.
10. 중요 포인트 녹음 STT가 여러 개면(같은 날·같은 레슨) 각각을 따로 글처럼 쓰지 말고, 하나의 레슨 일지로 시간 흐름에 맞게 모두 녹여 쓴다. 포인트마다 구체적 문제·팁을 빠뜨리지 않는다.
11. 응답은 반드시 JSON 객체만 출력한다.`;

const NAVER_SYSTEM_PROMPT = `당신은 네이버 블로그 SEO 전문 카피라이터입니다.
오프라인 실용음악학원 레슨 기록을 네이버 검색에 강한 친근한 블로그 글로 재작성합니다.
짧게 요약하지 말고, 현장 레슨 일지처럼 풍부하게 씁니다.

반드시 지킬 규칙:
1. 제목(title)은 [지역키워드] + [레슨 곡명/실제 고민] + [해결·후기 톤]으로 쓴다. 키워드만 나열하지 않는다.
   - 공백 포함 권장 32~55자(최대 58자). 학원명은 제목에 최대 1회.
   - 좋은 예: "화정역 보컬학원 레슨 일지: '그겨울' 고음 발음이 자꾸 씹힐 때 해결법"
   - 나쁜 예: "화정역 보컬학원에서 배우는 고양시 보컬 레슨" (키워드 조합만)
   - 원본/STT에 없는 곡명·고민은 지어내지 않는다.
2. 지역 키워드·목적어를 제목에 도배하지 않는다. "!" 남발 금지.
3. 본문 분량·구조 (필수):
   - 본문(body)은 빈 줄로 구분된 단락을 최소 5개, 권장 6~8개. (연락처 단락 제외)
   - 전체 본문 글자 수는 공백 제외 약 700자 이상(목표 900~1400자). 2~3단락짜리 짧은 글 금지.
   - 구성 예: (1) 오늘 레슨 한줄 도입 (2~N) STT 포인트별 장면 (N+1) 학원/CODA 한 단락 (마지막) 연락처 텍스트
4. STT/원본 클립마다 반드시:
   - 구체적 소리 문제 1문장 이상 (발음 씹힘, 턱 힘, 고음 막힘, 중심이 앞으로 쏠림 등 — STT에 나온 표현을 살려 씀)
   - 실제 코칭 팁 2문장 이상 (강사 말투·지시·교정 방법을 STT에서 가져와 풀어 씀)
   - 관련 가사 구절·곡명이 있으면 그대로 인용
   교과서적 일반론("발음이 중요해요" 수준)만 쓰는 것은 금지.
5. 영혼 없는 총평·마무리 문장 금지 (블랙리스트 예):
   "~진행되었답니다", "~경험할 수 있는 수업이었어요", "~유익한 시간이었습니다",
   "자신감을 얻었습니다", "연습하면 더 좋아질 거예요", "지속적인 연습으로", "많은 도움이 되었어요",
   "좋은 수업이었습니다", "만족스러운 레슨", "앞으로 기대됩니다"
   글은 마지막 코칭 팁·구체 장면으로 끝내고, 위 같은 추상 총평으로 끝내지 않는다.
6. 제공된 지역 키워드를 제목 앞쪽에 1개 이상, 본문에 합쳐 3~4회 자연스럽게 넣는다. 억지 반복 금지.
7. 문단은 2~4문장으로 끊고, 말하듯 친근한 톤(~해요/~예요). 단, 분량은 위 최소치를 지킨다.
8. [사진 추천: …]는 서로 다른 단락 아래에 3곳 이상. 각 태그는 한 줄에 하나만.
   - 본문 맨 아래·연락처 앞에 몰아넣기 금지.
   - 여러 장면을 한 줄에 쉼표로 나열하는 것도 금지. (예: "[사진 추천: A, B, C]" ❌)
   - 관련 이야기가 나온 단락 직후에 배치. (예: 발음 연습 단락 바로 다음 줄)
9. 네이버용 body에 마크다운 금지 (##, [이름](URL), **). 연락처는 일반 텍스트+단순 URL.
10. 티스토리 원고와 문장·단락 순서를 20% 이상 다르게. STT 디테일은 네이버에 더 또렷하게.
11. 원문에 없는 허위 수치·자격·성과·곡명·가사를 지어내지 않는다.
12. 수강생 실명·개인정보 금지. 이모지·키워드 도배 금지.
13. STT가 여러 개면 같은 날 레슨 일지 한 편에 포인트 순서로 모두 녹인다. 클립을 한 단락에 뭉개지 말고 클립당 최소 1단락.
14. 응답은 반드시 JSON 객체만 출력한다.`;

/** 네이버 제목: 과도한 길이만 잘라 낸다 */
export function normalizeNaverTitle(raw: string, fallback: string): string {
  let t = raw.replace(/\s+/g, " ").trim();
  if (!t) t = fallback;
  const maxLen = 58;
  if (t.length > maxLen) {
    const cut = t.slice(0, maxLen);
    const breakAt = Math.max(
      cut.lastIndexOf(" "),
      cut.lastIndexOf("|"),
      cut.lastIndexOf("—"),
      cut.lastIndexOf("-"),
      cut.lastIndexOf(","),
      cut.lastIndexOf(":"),
    );
    t = (breakAt >= 24 ? cut.slice(0, breakAt) : cut).trim();
  }
  return t;
}

/** 네이버 붙여넣기용: 마크다운 헤딩·링크 등을 일반 텍스트로 */
export function stripNaverMarkdown(raw: string): string {
  let s = raw.replace(/\r\n/g, "\n");
  // [라벨](url) → 라벨 url  (단, [사진 추천: …] 가이드는 제외)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_m, label: string, url: string) => {
    const t = String(label).trim();
    if (/^사진\s*추천\s*:/i.test(t)) return `[${t}]`;
    return `${t} ${url}`.trim();
  });
  // 줄 시작 헤딩 ## / # / ###
  s = s.replace(/^#{1,6}\s+/gm, "");
  // **bold** / *italic* (단순)
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "$1");
  // 마크다운 리스트 "- " 를 유지하되 과도한 "**" 등은 위에서 처리
  s = s.replace(/\n{3,}/g, "\n\n");
  return s.trim();
}

function academyBlock(academy: AeoAcademyProfile): string {
  return `[학원 프로필 — 명칭 변경 금지]
- 학원명: ${academy.name}
- 위치: ${academy.location}
- 주소: ${academy.address}
- 전화: ${academy.phone}
- 웹사이트: ${academy.url}
- 주요 서비스: ${academy.services.join(", ")}
- 근거/수치 문구: ${academy.evidence}`;
}

function parseFaq(raw: unknown): AeoFaqItem[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const o = item as Record<string, unknown>;
      const question = String(o.question ?? o.q ?? "").trim();
      const answer = String(o.answer ?? o.a ?? "").trim();
      if (!question || !answer) return null;
      return { question, answer };
    })
    .filter((x): x is AeoFaqItem => !!x);
}

/** 학원 위치·서비스로 네이버용 지역 키워드 후보 생성 */
export function buildNaverLocalKeywords(academy: AeoAcademyProfile): string[] {
  const blob = `${academy.location ?? ""} ${academy.address ?? ""}`.trim();
  const primary =
    (academy.services.find((s) => s.includes("보컬")) || academy.services[0] || "보컬").trim() ||
    "보컬";

  const stationMatch = blob.match(/([가-힣A-Za-z0-9]+역)/);
  const cityMatch = blob.match(
    /(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|[가-힣]+시|[가-힣]+군)/,
  );
  const districtMatch = blob.match(/([가-힣]+구)/);

  const station = stationMatch?.[1] ?? "";
  const city = (cityMatch?.[1] ?? "")
    .replace(/특별시$/, "시")
    .replace(/광역시$/, "시")
    .replace(/특별자치시$/, "시");
  const placeShort = station
    ? station.replace(/역$/, "")
    : districtMatch?.[1]
      ? districtMatch[1].replace(/구$/, "")
      : "";

  const out: string[] = [];
  const push = (s: string) => {
    const t = s.replace(/\s+/g, " ").trim();
    if (t && !out.includes(t)) out.push(t);
  };

  if (station) push(`${station} ${primary}학원`);
  if (city) push(`${city} ${primary} 레슨`);
  if (placeShort) push(`${placeShort} 성인 ${primary}`);
  if (station && primary !== "보컬") push(`${station} 보컬학원`);
  if (city && !out.some((k) => k.includes("보컬"))) push(`${city} 보컬 레슨`);
  if (placeShort && academy.name) push(`${placeShort} ${academy.name.replace(/\s+/g, " ").trim()}`);

  // 프로필에 위치 정보가 거의 없을 때 최소 키워드
  if (!out.length) {
    push(`${academy.name} ${primary} 레슨`);
    push(`${primary}학원 후기`);
    push(`성인 ${primary} 레슨`);
  }

  return out.slice(0, 6);
}

export function articleToMarkdown(article: AeoArticle): string {
  const parts = [
    `# ${article.title}`,
    "",
    article.oneSentenceAnswer,
    "",
    article.markdownBody.trim(),
  ];
  if (article.faq.length) {
    parts.push("", "## 자주 묻는 질문");
    for (const item of article.faq) {
      parts.push(`### ${item.question}`, item.answer, "");
    }
  }
  return parts.join("\n").trim() + "\n";
}

export function naverArticleToPlain(article: NaverBlogArticle): string {
  return `${article.title}\n\n${article.body.trim()}\n`.trim() + "\n";
}

async function openAiJson(
  system: string,
  user: string,
  temperature: number,
): Promise<Record<string, unknown>> {
  const key = process.env.OPENAI_API_KEY?.trim();
  if (!key) throw new Error("OPENAI_API_KEY가 필요합니다 (AEO).");
  const model = (process.env.OPENAI_AEO_MODEL || process.env.OPENAI_MODEL || "gpt-4o-mini").trim();

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      temperature,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`AEO OpenAI 실패 HTTP ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };
  const raw = data.choices?.[0]?.message?.content || "{}";
  return JSON.parse(raw) as Record<string, unknown>;
}

export async function optimizeLessonToAeo(
  sourceText: string,
  academy: AeoAcademyProfile,
): Promise<AeoArticle> {
  const userPrompt = `${academyBlock(academy)}

[원본 — CODA 레슨 기록 (익명화됨)]
${sourceText}

위 원본을 티스토리용 AEO 최적화 블로그 포스트 JSON으로 변환하세요.
필드는 title, one_sentence_answer, markdown_body, faq(배열:{question,answer}), keywords(문자열 배열), meta_description 입니다.
title에는 '${academy.name}'과 위치 키워드를 자연스럽게 포함하세요.
중요 포인트 녹음 STT가 여러 개면 하나의 레슨 일지로 모두 녹여 쓰고, 포인트별 구체적 내용이 빠지지 않게 하세요.
데이터·Q&A·사실 중심, 텍스트 위주 Markdown으로 작성하세요.`;

  const parsed = await openAiJson(AEO_SYSTEM_PROMPT, userPrompt, 0.4);

  return {
    title: String(parsed.title ?? "").trim() || `${academy.name} 레슨 기록`,
    oneSentenceAnswer: String(
      parsed.one_sentence_answer ?? parsed.oneSentenceAnswer ?? "",
    ).trim(),
    markdownBody: String(parsed.markdown_body ?? parsed.markdownBody ?? "").trim(),
    faq: parseFaq(parsed.faq),
    keywords: Array.isArray(parsed.keywords)
      ? parsed.keywords.map((k) => String(k).trim()).filter(Boolean)
      : [],
    metaDescription: String(
      parsed.meta_description ?? parsed.metaDescription ?? "",
    ).trim(),
  };
}

export async function optimizeLessonToNaverSeo(
  sourceText: string,
  academy: AeoAcademyProfile,
  tistoryArticle: AeoArticle,
): Promise<NaverBlogArticle> {
  const localKeywords = buildNaverLocalKeywords(academy);
  const tistoryPlain = articleToMarkdown(tistoryArticle);

  const userPrompt = `${academyBlock(academy)}

[네이버 SEO 필수 지역 키워드 — 제목·본문에 자연스럽게 사용]
${localKeywords.map((k, i) => `${i + 1}. ${k}`).join("\n")}

[원본 — CODA 레슨 기록 (익명화됨)]
${sourceText}

[티스토리/AEO용 원고 — 이와 문장·구조 20% 이상 다르게 쓸 것]
${tistoryPlain}

위 원본을 네이버 블로그 SEO용 JSON으로 작성하세요.
필드는 title, body, keywords(문자열 배열), meta_description 입니다.
- title: [지역키워드] + [레슨 곡명/실제 고민] + [해결·후기 톤]. 키워드만 나열 금지. 최대 58자. 학원명 최대 1회.
  예) "${localKeywords[0] || "화정역 보컬학원"} 레슨 일지: '그겨울' 고음 발음이 자꾸 씹힐 때 해결법"
- body (짧게 쓰지 말 것):
  · 단락 최소 5개(권장 6~8), 공백 제외 약 700자 이상
  · STT 클립마다: 소리 문제 1문장 + 코칭 팁 2문장 이상, 가사/곡명 생생히. 클립당 최소 1단락
  · 총평 금지(자신감/연습하면/유익한 시간/진행되었답니다 등). 구체 팁으로 끝내기
  · [사진 추천: …] 서로 다른 단락 직후 3곳(한 줄에 장면 나열·맨 아래 몰기 금지)
  · 마크다운 금지. 연락처는 "전화: … / 주소: … / 웹사이트: https://…" 일반 텍스트
- keywords: 지역 키워드 + 학원명·서비스·곡/문제 태그
티스토리와 표현을 다르게 하되 STT 디테일은 네이버에 더 풍부하게 펼치세요.`;

  const parsed = await openAiJson(NAVER_SYSTEM_PROMPT, userPrompt, 0.72);
  const rawBody = String(parsed.body ?? parsed.markdown_body ?? parsed.markdownBody ?? "").trim();
  const body = stripNaverMarkdown(
    rawBody ||
      `${localKeywords[0] || academy.name}에서 진행한 레슨 기록입니다.\n\n[사진 추천: 레슨실 내부 또는 악보 이미지]\n`,
  );
  const keywords = Array.isArray(parsed.keywords)
    ? parsed.keywords.map((k) => String(k).trim()).filter(Boolean)
    : localKeywords;
  const fallbackTitle = `${localKeywords[0] || academy.name} 레슨 후기`;

  return {
    title: normalizeNaverTitle(String(parsed.title ?? ""), fallbackTitle),
    body,
    keywords: keywords.length ? keywords : localKeywords,
    metaDescription: String(
      parsed.meta_description ?? parsed.metaDescription ?? "",
    ).trim(),
  };
}

/** 티스토리(AEO) + 네이버(SEO) 동시 생성 */
export async function optimizeLessonToDualChannels(
  sourceText: string,
  academy: AeoAcademyProfile,
): Promise<{ tistory: AeoArticle; naver: NaverBlogArticle }> {
  const tistory = await optimizeLessonToAeo(sourceText, academy);
  const naver = await optimizeLessonToNaverSeo(sourceText, academy, tistory);
  return { tistory, naver };
}
