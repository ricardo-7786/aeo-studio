import { parseAcademyAssignment } from "@shared/academyAssignment";
import type { AcademyAeoProfile as AcademyAeoProfileRow, User } from "@shared/schema";
import type { AeoAcademyProfile } from "./types";

function env(key: string, fallback = ""): string {
  return (process.env[key] ?? fallback).trim();
}

export function resolveLessonAcademyKey(
  teacher?: User | null,
  student?: User | null,
): string {
  const fromTeacher = parseAcademyAssignment(teacher?.academyName).academyName.trim();
  if (fromTeacher) return fromTeacher;
  return parseAcademyAssignment(student?.academyName).academyName.trim();
}

export function rowToAeoAcademyProfile(row: AcademyAeoProfileRow): AeoAcademyProfile {
  const services = String(row.services ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const lat = row.geoLat?.trim() ? Number(row.geoLat) : null;
  const lng = row.geoLng?.trim() ? Number(row.geoLng) : null;
  return {
    name: row.name,
    location: row.location ?? "",
    address: row.address ?? "",
    phone: row.phone ?? "",
    url: row.url ?? "",
    services,
    evidence: row.evidence ?? "",
    geoLat: lat != null && !Number.isNaN(lat) ? lat : null,
    geoLng: lng != null && !Number.isNaN(lng) ? lng : null,
    priceRange: row.priceRange || "$$",
    openingHours: row.openingHours || "",
  };
}

/** .env → 프로필 시드용 (오엠에이 등 첫 배포 보강) */
export function aeoProfileFromEnv(): {
  academyKey: string;
  name: string;
  location: string;
  address: string;
  phone: string;
  url: string;
  services: string;
  evidence: string;
  geoLat: string | null;
  geoLng: string | null;
  priceRange: string;
  openingHours: string;
} | null {
  const name = env("AEO_ACADEMY_NAME");
  if (!name) return null;
  return {
    academyKey: name,
    name,
    location: env("AEO_ACADEMY_LOCATION"),
    address: env("AEO_ACADEMY_ADDRESS"),
    phone: env("AEO_ACADEMY_PHONE"),
    url: env("AEO_ACADEMY_URL"),
    services: env("AEO_ACADEMY_SERVICES", "보컬, 미디작곡, 기타, 피아노"),
    evidence: env("AEO_ACADEMY_EVIDENCE"),
    geoLat: env("AEO_ACADEMY_GEO_LAT") || null,
    geoLng: env("AEO_ACADEMY_GEO_LNG") || null,
    priceRange: env("AEO_ACADEMY_PRICE_RANGE", "$$"),
    openingHours: env("AEO_ACADEMY_OPENING_HOURS", "Mo-Fr 14:00-22:00, Sa 13:00-19:00"),
  };
}

export class AeoProfileRequiredError extends Error {
  readonly code = "AEO_PROFILE_REQUIRED" as const;
  constructor(
    public academyKey: string,
    message?: string,
  ) {
    super(
      message ||
        (academyKey
          ? `"${academyKey}" 학원 AEO 프로필이 없습니다. 먼저 학원 정보를 저장해 주세요.`
          : "학원 AEO 프로필이 없습니다. 학원명을 포함해 프로필을 저장해 주세요."),
    );
    this.name = "AeoProfileRequiredError";
  }
}
