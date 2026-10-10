/**
 * 상장일 표시 (014 반복 2026-10-10f — FR-033, contracts D12, research R14-26).
 *
 * **기준을 함께 보인다.** 키움 국내 상장일만 상장일이다. Yahoo 첫 거래일은 출처가 시세를 가진 첫 날이라 그보다 앞서 상장한 종목은 실제
 * 상장일보다 늦고(T158 — 도요타 1999-05-06, 1949년 상장), 코인 첫 일봉은 출처의 첫 일봉이지 거래소 상장일이 아니다. 기준 없이 "상장"이라
 * 쓰면 틀린 날짜가 상장일로 읽힌다. 검색 결과 줄·비교 표가 이 한 곳의 글자를 쓴다.
 */
import type { ListingBasis } from "./types";

export interface ListingLabel {
  text: string;
  title: string;
}

const WORD: Record<ListingBasis, string> = { listing: "상장", first_trade: "첫 거래", first_bar: "첫 일봉" };

const TITLE: Record<ListingBasis, string> = {
  listing: "키움 종목 정보의 상장일",
  first_trade: "시세 출처(Yahoo)가 시세를 가진 첫 날 — 그보다 앞서 상장한 종목은 실제 상장일보다 늦습니다",
  first_bar: "출처(investing.com)의 첫 일봉 — 거래소 상장일이 아닙니다",
};

/** 비교 표 칸 아래의 작은 글자. 키움 상장일은 상장일 그대로라 없다. */
export const LISTING_NOTE: Record<ListingBasis, string | null> = {
  listing: null, first_trade: "첫 거래일", first_bar: "첫 일봉",
};

/** 모르는 상장일의 까닭 — 지어내지 않는다(헌법 원칙 V). */
export const LISTING_UNKNOWN =
  "출처가 상장일을 주지 않았습니다 — 주식은 종목을 고르면 받아 두고, 가상자산은 첫 일봉을 알게 되면 보입니다";

export function listingTitle(basis: ListingBasis): string {
  return TITLE[basis];
}

const label = (basis: ListingBasis, date: string): ListingLabel => ({ text: `${WORD[basis]} ${date}`, title: TITLE[basis] });

/** 주식 검색 결과 줄 — 키움 상장일 → 저장된 Yahoo 첫 거래일. 둘 다 없으면 `null`(그 글자를 뺀다). */
export function stockListingLabel(listedOn: string | null | undefined, firstTradedOn: string | null | undefined): ListingLabel | null {
  if (listedOn) return label("listing", listedOn);
  if (firstTradedOn) return label("first_trade", firstTradedOn);
  return null;
}

/** 코인 검색 결과 줄 — 수집으로 알게 된 첫 일봉. 없으면 `null`. */
export function coinListingLabel(firstAvailableDate: string | null): ListingLabel | null {
  return firstAvailableDate ? label("first_bar", firstAvailableDate) : null;
}
