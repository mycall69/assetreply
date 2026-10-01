/**
 * 시뮬레이션 이력 보관 테스트 (T084, T085) — 005 FR-036, FR-037, SC-014, R5-9·R5-10.
 *
 * **조건만 저장한다.** 결과는 시세·설정·환율의 함수이고 그중 설정과 환율이 바뀐다.
 * 저장하면 갱신 시점을 관리해야 하고, 그 관리가 틀리면 **조용히 낡은 값을 보여준다**
 * (R5-9). 조건은 사용자가 고른 값이라 바뀌지 않는다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  HISTORY_KEY,
  conditionId,
  loadHistory,
  removeHistory,
  saveHistory,
} from "@/lib/simulationHistory";
import type { HistoryCondition } from "@/lib/simulationHistory";
import type { StockSearchResult } from "@/lib/types";

const SAMSUNG: StockSearchResult = {
  market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW",
};
const APPLE: StockSearchResult = {
  market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD",
};

const condition = (over: Partial<HistoryCondition> = {}): HistoryCondition => ({
  stock: SAMSUNG,
  start: "2021-08-01",
  principal: "86997",
  principalCurrency: "KRW",
  reinvest: true,
  ...over,
});

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("이력 보관", () => {
  it("종목·시작일·원금·재투자 여부가 모두 남는다", () => {
    // FR-036, SC-014 — 종목명만 남으면 같은 종목의 다른 조건을 구분할 수 없다.
    saveHistory(condition());
    const [entry] = loadHistory();
    expect(entry.stock.name).toBe("삼성전자");
    expect(entry.start).toBe("2021-08-01");
    expect(entry.principal).toBe("86997");
    expect(entry.principalCurrency).toBe("KRW");
    expect(entry.reinvest).toBe(true);
  });

  it("같은 종목의 다른 조건을 구별한다", () => {
    // 재투자만 다른 두 건이다. 합쳐지면 사용자는 둘 중 하나를 잃는다.
    saveHistory(condition({ reinvest: true }));
    saveHistory(condition({ reinvest: false }));
    expect(loadHistory()).toHaveLength(2);
  });

  it("같은 조건을 다시 저장해도 늘지 않는다", () => {
    // 같은 조건을 여러 번 돌리는 것이 보통이다. 매번 쌓이면 목록이 못 쓰게 된다.
    saveHistory(condition());
    saveHistory(condition());
    expect(loadHistory()).toHaveLength(1);
  });

  it("최근 것이 앞에 온다", () => {
    saveHistory(condition());
    saveHistory(condition({ stock: APPLE, principalCurrency: "KRW" }));
    expect(loadHistory()[0].stock.symbol).toBe("AAPL");
  });

  it("브라우저를 닫았다 열어도 남는다", () => {
    // FR-037 — 세션 저장소였다면 탭을 닫는 순간 사라진다.
    saveHistory(condition());
    const raw = localStorage.getItem(HISTORY_KEY);
    expect(raw).not.toBeNull();
    // 모듈 상태가 아니라 저장소에서 읽는다는 것을 보인다.
    expect(JSON.parse(raw as string)).toHaveLength(1);
  });

  it("결과를 저장하지 않는다", () => {
    // R5-9 — 수익률은 설정·환율이 바뀌면 달라진다. 저장하면 조용히 낡는다.
    saveHistory(condition());
    const stored = JSON.parse(localStorage.getItem(HISTORY_KEY) as string);
    expect(JSON.stringify(stored)).not.toContain("returnRate");
    expect(JSON.stringify(stored)).not.toContain("balance");
  });

  it("항목을 지울 수 있다", () => {
    // FR-037b — 지울 수 없으면 쌓이기만 하고 시스템이 임의로 버리게 된다.
    saveHistory(condition());
    saveHistory(condition({ reinvest: false }));
    const target = loadHistory()[0].id;
    removeHistory(target);
    expect(loadHistory().map((e) => e.id)).not.toContain(target);
    expect(loadHistory()).toHaveLength(1);
  });

  it("같은 조건은 같은 식별자를 갖는다", () => {
    expect(conditionId(condition())).toBe(conditionId(condition()));
    expect(conditionId(condition())).not.toBe(
      conditionId(condition({ reinvest: false })),
    );
  });

  it("저장소가 깨져 있으면 빈 목록으로 시작한다", () => {
    // 던지면 화면 전체가 죽는다. 이력은 부가 기능이라 본 기능을 막으면 안 된다.
    localStorage.setItem(HISTORY_KEY, "{이건 JSON이 아니다");
    expect(loadHistory()).toEqual([]);
  });
});

describe("저장 실패", () => {
  it("보관 한계에 닿으면 알린다", () => {
    // R5-10 — 조용히 실패하면 사용자는 저장된 줄 알고 다음에 열었을 때 비어 있다.
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    const result = saveHistory(condition());
    expect(result.ok).toBe(false);
    expect(result.ok === false && result.reason).toMatch(/저장/);
  });

  it("성공하면 사유가 없다", () => {
    const result = saveHistory(condition());
    expect(result.ok).toBe(true);
  });

  it("실패해도 이미 있던 이력을 잃지 않는다", () => {
    saveHistory(condition());
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    saveHistory(condition({ stock: APPLE }));
    vi.restoreAllMocks();
    expect(loadHistory()).toHaveLength(1);
  });
});
