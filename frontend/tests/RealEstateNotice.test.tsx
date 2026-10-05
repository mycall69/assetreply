/**
 * 부동산 보드 아래 안내 줄 (T034) — 009 FR-010, FR-014, FR-018, FR-021, FR-026, ui-wireframes E4.
 *
 * 해당할 때만, **이 순서대로** 한 줄씩 — 알림 역할(`role="status"`, 005~008과 같다).
 * 1. **잠정** — 잠정 기간과 "바뀔 수 있다"와 그 이유 둘(최근 3개월은 신고가 더 들어오고, 그 앞은 해제가 늦게 반영된다).
 *    지금 시세가 잠정 거래를 쓸 때(`summary.provisional`). 하나라도 빠지면 잠정 값을 확정 값으로 읽는다
 * 2. **지금 시세 없음** — 마지막으로 시세가 있던 달과 "그 달까지의 결과"(FR-026)
 * 3. **보유세 계산 불가** — 6월 시세가 없어 계산하지 못한 해를 모두(`summary.taxGaps`, FR-021). 누적 비용이 실제보다 작다
 * 4. **확인 실패** — 받아 둔 거래로 계산했고 내일 다시 확인한다. 인증·형식이면 할 일을 붙인다(008 D3과 같다, FR-014)
 *
 * ## 이 테스트가 전제하는 모듈 (T039가 따른다)
 *
 * `@/components/realestate/RealEstateNotice` — `export function RealEstateNotice({ summary })`, `summary: RealEstateSummary`.
 * 잠정 기간은 **`summary.provisionalFrom`의 달부터 `summary.asOf`의 달까지**다 — 기간의 길이는 서버 설정
 * (`APT_TRADE_PROVISIONAL_MONTHS`, 기본 12개월)이 정한다. 화면이 12개월을 세면 설정을 바꿨을 때 안내가 실제 잠정 기간과 어긋난다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RealEstateNotice } from "@/components/realestate/RealEstateNotice";
import type { RealEstateFailureKind, RealEstateSummary } from "@/lib/types";
import { SIM_SUMMARY } from "./support/realEstateSimulationFixtures";

/** 잠정도 아니고 실패도 없는 요약. */
const CLEAN: RealEstateSummary = { ...SIM_SUMMARY, estimated: false, provisional: false };
/** 지금 시세가 없다 — 마지막 시세 달까지의 결과다. 시세가 없으니 잠정도 아니다. */
const NO_VALUE: RealEstateSummary = {
  ...CLEAN, value: null, valueMonth: null, valueWindow: null, lastPricedMonth: "2024-02",
};

const lines = () => screen.getAllByRole("status").map((s) => s.textContent ?? "");

describe("부동산 안내 줄", () => {
  it("해당하는 것이 없으면 아무것도 보이지 않는다", () => {
    const { container } = render(<RealEstateNotice summary={CLEAN} />);
    expect(container.textContent).toBe("");
  });

  it("잠정 — 잠정 기간과 바뀔 수 있다는 사실과 이유 둘", () => {
    render(<RealEstateNotice summary={SIM_SUMMARY} />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("잠정");
    expect(line).toContain("2025-11 ~ 2026-10");
    expect(line).toContain("바뀔 수 있습니다");
    expect(line).toContain("최근 3개월은 신고가 더 들어오고");
    expect(line).toContain("해제가 늦게 반영됩니다");
    expect(line).toContain("지금 시세가 이 거래를 씁니다");
  });

  it("잠정 기간은 서버가 준 시작 달을 따른다 — 설정이 6개월이면 6개월", () => {
    render(<RealEstateNotice summary={{ ...SIM_SUMMARY, provisionalFrom: "2026-05-01" }} />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("2026-05 ~ 2026-10");
    expect(line).not.toContain("2025-11");
    expect(line).not.toContain("12개월");
  });

  it("잠정 기간의 끝은 오늘의 달이다 — 해가 바뀌어도", () => {
    render(<RealEstateNotice summary={{ ...SIM_SUMMARY, asOf: "2026-03-02", provisionalFrom: "2025-04-01" }} />);
    expect(screen.getByRole("status").textContent).toContain("2025-04 ~ 2026-03");
  });

  it("지금 시세 없음 — 마지막으로 시세가 있던 달까지의 결과다", () => {
    render(<RealEstateNotice summary={NO_VALUE} />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("지금 시세 없음");
    expect(line).toContain("36개월 안에 거래가 없습니다");
    expect(line).toContain("2024-02까지의 결과입니다");
  });

  it("보유세 계산 불가 — 그 해들을 모두 적고 누적 비용이 작다고 말한다", () => {
    render(<RealEstateNotice summary={{ ...CLEAN, taxGaps: [2019, 2020] }} />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("2019년");
    expect(line).toContain("2020년");
    expect(line).toContain("보유세를 계산하지 못했습니다(6월 시세 없음)");
    expect(line).toContain("누적 비용이 실제보다 작습니다");
  });

  it("확인 실패 — 받아 둔 거래로 계산했고 내일 다시 확인한다", () => {
    render(<RealEstateNotice summary={{ ...CLEAN, recheckFailed: { kind: "network", reason: "연결 끊김" } }} />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("오늘 실거래 확인에 실패했습니다");
    expect(line).toContain("받아 둔 거래로 계산했습니다");
    expect(line).toContain("내일 다시 확인합니다");
  });

  it.each([
    ["auth", "인증키 설정을 확인하세요"],
    ["format", "어댑터를 고쳐야 합니다"],
  ] as const)("확인 실패(%s)면 할 일을 붙인다", (kind, action) => {
    render(<RealEstateNotice summary={{ ...CLEAN, recheckFailed: { kind, reason: "사유" } }} />);
    expect(screen.getByRole("status").textContent).toContain(action);
  });

  it.each<RealEstateFailureKind>(["rate_limited", "network"])(
    "확인 실패(%s)는 기다리면 되므로 할 일을 붙이지 않는다", (kind) => {
      render(<RealEstateNotice summary={{ ...CLEAN, recheckFailed: { kind, reason: "사유" } }} />);
      const line = screen.getByRole("status").textContent ?? "";
      expect(line).toMatch(/내일 다시 확인합니다\.$/);
      expect(line).not.toContain("인증키 설정");
      expect(line).not.toContain("어댑터");
    });

  it("순서 — 잠정 · 보유세 계산 불가 · 확인 실패", () => {
    render(<RealEstateNotice summary={{ ...SIM_SUMMARY, taxGaps: [2019],
      recheckFailed: { kind: "auth", reason: "사유" } }} />);
    const shown = lines();
    expect(shown).toHaveLength(3);
    expect(shown[0]).toContain("잠정");
    expect(shown[1]).toContain("2019년");
    expect(shown[2]).toContain("오늘 실거래 확인에 실패했습니다");
  });

  it("순서 — 지금 시세 없음 · 보유세 계산 불가 · 확인 실패", () => {
    render(<RealEstateNotice summary={{ ...NO_VALUE, taxGaps: [2019],
      recheckFailed: { kind: "rate_limited", reason: "사유" } }} />);
    const shown = lines();
    expect(shown).toHaveLength(3);
    expect(shown[0]).toContain("지금 시세 없음");
    expect(shown[1]).toContain("2019년");
    expect(shown[2]).toContain("오늘 실거래 확인에 실패했습니다");
  });
});
