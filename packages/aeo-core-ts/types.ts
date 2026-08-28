/** CODA → AEO(Answer Engine Optimization) 홍보글 생성 */

export type AeoAcademyProfile = {
  name: string;
  location: string;
  address: string;
  phone: string;
  url: string;
  services: string[];
  evidence: string;
  geoLat?: number | null;
  geoLng?: number | null;
  priceRange?: string;
  openingHours?: string;
};

export type AeoFaqItem = {
  question: string;
  answer: string;
};

export type AeoArticle = {
  title: string;
  oneSentenceAnswer: string;
  markdownBody: string;
  faq: AeoFaqItem[];
  keywords: string[];
  metaDescription: string;
};

/** 네이버 블로그 SEO 전용 초안 */
export type NaverBlogArticle = {
  title: string;
  /** 짧은 문단 + [사진 추천: …] 가이드가 포함된 본문 */
  body: string;
  keywords: string[];
  metaDescription: string;
};

export type AeoDraftResult = {
  article: AeoArticle;
  markdown: string;
  /** 티스토리(AEO)와 동시에 생성되는 네이버 SEO 버전 */
  naver: NaverBlogArticle;
  jsonLd: Record<string, unknown>;
  sourceText: string;
  sttSnippets: { recordingId: number; title: string; text: string }[];
  generatedAt: string;
};
