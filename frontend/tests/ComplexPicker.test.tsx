/**
 * 단지 고르기 (T020) — 009 FR-003, FR-011, FR-014, FR-015, ui-wireframes E1·E2·E9·접근성.
 *
 * - 항목은 "단지명 · YYYY년 입주 · N세대"(가구수 3자리 쉼표). 세대수를 모르면 "단지명 · YYYY년 입주"만 — **지어내지 않는다**
 * - **같은 동에 이름이 같은 단지가 둘 이상이면 둘 다 항목 끝에 지번**을 붙인다. 이름이 겹치지 않으면 붙이지 않는다 — 같은 글자의 항목
 *   둘 중 무엇이 어느 단지인지 가를 수 없으면 엉뚱한 단지의 시세를 본다
 * - 기본 정보를 채우는 동안 "세대수·입주년도를 채우고 있습니다 | 12 / 47단지"
 * - 그 시·군·구의 실거래를 받는 동안 "송파구 실거래를 받고 있습니다 | 120 / 250개월"(006 `CollectingNotice`, 주어·단위는 008의 선택
 *   속성)과 "처음 고르는 시·군·구는 전체 이력을 받습니다"
 * - 단지 목록 자료를 받지 못하면(`listError`) 빈 풀다운 대신 사유(`role="alert"`, FR-015)
 * - **실거래 수집이 실패했으면**(`trades.state = "failed"`) E9의 종류별 문구·할 일(`role="alert"`, FR-014) — 다시 열어도 보인다
 *
 * ## 이 테스트가 전제하는 모듈 (T026이 따른다)
 *
 * `@/components/realestate/ComplexPicker` — `export function ComplexPicker(props)`
 * - `complexes: RealEstateComplexesResponse | null` — 동을 고르기 전 `null`(풀다운 비활성)
 * - `value: number | null` — 고른 `complexId`
 * - `onChange: (complexId: number) => void`
 * - `sggName: string | null` — 실거래 진행 줄의 주어("송파구")
 * - `tradeProgress: RealEstateProgressSnapshot | null` — 실거래 작업의 진행. 없으면 응답의 `trades.monthsDone`·`monthsTotal`
 * - `detailsProgress: RealEstateProgressSnapshot | null` — 기본 정보 작업의 진행(받은 단지 / 단지 수)
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { ComplexPicker } from "@/components/realestate/ComplexPicker";
import type { RealEstateFailureKind } from "@/lib/types";
import {
  COLLECTING_TRADES,
  FAILURE_FRAGMENTS,
  FAILURE_KINDS,
  GARAK_COMPLEXES,
  GARAK_FIRST,
  HELIO,
  HELIO_ID,
  HYUNJIN,
  complexesWith,
  failedTrades,
} from "./support/realEstateFixtures";

type Props = ComponentProps<typeof ComplexPicker>;

const BASE: Props = {
  complexes: GARAK_COMPLEXES,
  value: null,
  onChange: () => undefined,
  sggName: "송파구",
  tradeProgress: null,
  detailsProgress: null,
};

function renderPicker(over: Partial<Props> = {}) {
  const onChange = vi.fn();
  render(<ComplexPicker {...BASE} onChange={onChange} {...over} />);
  return onChange;
}

const complexSelect = () => screen.getByRole("combobox", { name: "단지" });
/** 고를 수 있는 항목의 글자 — 빈 값(안내) 항목은 뺀다. */
const choices = () =>
  within(complexSelect()).getAllByRole("option")
    .filter((o) => (o as HTMLOptionElement).value !== "")
    .map((o) => o.textContent);

describe("단지 풀다운", () => {
  it("label이 붙은 select다", () => {
    renderPicker();
    expect(screen.getByLabelText("단지").tagName).toBe("SELECT");
  });

  it("동을 고르기 전에는 쓸 수 없다", () => {
    renderPicker({ complexes: null });
    expect(complexSelect()).toBeDisabled();
  });

  it("항목은 단지명 · 입주년도 · 세대수(쉼표)이고, 세대수를 모르면 입주년도까지만이다", () => {
    renderPicker({ complexes: complexesWith({ items: [HELIO, HYUNJIN] }) });
    expect(choices()).toEqual(["헬리오시티 · 2018년 입주 · 9,510세대", "현진타워 · 2015년 입주"]);
  });

  it("입주년도도 모르면 이름만 보인다 — 지어내지 않는다", () => {
    renderPicker({ complexes: GARAK_FIRST });
    expect(choices()).toEqual(["헬리오시티"]);
  });

  it("같은 이름 단지가 둘이면 둘 다 끝에 지번을 붙이고, 이름이 겹치지 않는 단지에는 붙이지 않는다", () => {
    renderPicker();
    expect(choices()).toEqual([
      "헬리오시티 · 2018년 입주 · 9,510세대",
      "현대 · 1998년 입주 · 500세대 · 140",
      "현대 · 2003년 입주 · 140-2",
      "현진타워 · 2015년 입주",
    ]);
  });

  it("고르기 전에는 빈 값이다", () => {
    renderPicker();
    expect(complexSelect()).toHaveValue("");
  });

  it("고르면 단지 id를 숫자로 알린다", async () => {
    const onChange = renderPicker();
    await userEvent.selectOptions(complexSelect(), "헬리오시티 · 2018년 입주 · 9,510세대");
    expect(onChange).toHaveBeenCalledWith(HELIO_ID);
  });

  it("고른 단지가 풀다운의 값이다", () => {
    renderPicker({ value: HELIO_ID });
    expect(complexSelect()).toHaveValue(String(HELIO_ID));
  });
});

describe("기본 정보 진행", () => {
  it("세대수·입주년도를 채우는 동안 받은 단지 / 단지 수를 보인다", () => {
    renderPicker({
      complexes: GARAK_FIRST,
      detailsProgress: { jobId: 11, kind: "complex_details", target: "1171010700", status: "running", done: 12, total: 47 },
    });
    expect(screen.getByText(/세대수·입주년도를 채우고 있습니다/)).toBeInTheDocument();
    expect(screen.getByText(/12 \/ 47단지/)).toBeInTheDocument();
  });

  it("다 채웠으면 그 줄이 없다", () => {
    renderPicker();
    expect(screen.queryByText(/세대수·입주년도를 채우고 있습니다/)).toBeNull();
  });
});

describe("실거래 진행", () => {
  const collecting = complexesWith({ trades: COLLECTING_TRADES });

  it("그 시·군·구의 실거래를 받는 동안 받은 달 / 받을 달을 개월로 보인다", () => {
    renderPicker({ complexes: collecting });
    expect(screen.getByText(/송파구의? 실거래를 받고 있습니다/)).toBeInTheDocument();
    expect(screen.getByText(/120 \/ 250개월/)).toBeInTheDocument();
    const bars = screen.getAllByRole("progressbar");
    expect(bars.some((b) => b.getAttribute("aria-valuenow") === "120"
      && b.getAttribute("aria-valuemax") === "250")).toBe(true);
  });

  it("진행이 오면 그 수로 바꾼다", () => {
    renderPicker({
      complexes: collecting,
      tradeProgress: { jobId: 9, kind: "trade", target: "11710", status: "running", done: 130, total: 250 },
    });
    expect(screen.getByText(/130 \/ 250개월/)).toBeInTheDocument();
    expect(screen.queryByText(/120 \/ 250개월/)).toBeNull();
  });

  it("처음 고르는 시·군·구는 전체 이력을 받는다고 알리고, 끝나면 단지가 더해진다고 말한다", () => {
    renderPicker({ complexes: collecting });
    expect(screen.getByText(/처음 고르는 시·군·구는 전체 이력을 받습니다/)).toBeInTheDocument();
    expect(screen.getByText(/끝나면 단지 목록에 없던 단지가 더해집니다/)).toBeInTheDocument();
  });

  it("다 받은 시·군·구에는 진행 줄도 안내도 없다", () => {
    renderPicker();
    expect(screen.queryByText(/실거래를 받고 있습니다/)).toBeNull();
    expect(screen.queryByText(/전체 이력을 받습니다/)).toBeNull();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

describe("실패", () => {
  it("단지 목록을 받지 못했으면 사유와 함께 실거래 단지만 보인다고 알린다(FR-015)", () => {
    renderPicker({
      complexes: complexesWith({ items: [HYUNJIN], listError: { kind: "auth", reason: "인증키 오류" } }),
    });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("단지 목록을 받지 못했습니다(인증키 오류)");
    expect(alert).toContain("실거래를 받은 단지만 보입니다");
    expect(choices()).toEqual(["현진타워 · 2015년 입주"]);
  });

  it.each<RealEstateFailureKind>(FAILURE_KINDS)(
    "실거래 수집이 실패했으면 종류별 문구와 할 일을 보인다 — %s (FR-014)", (kind) => {
      renderPicker({ complexes: complexesWith({ trades: failedTrades(kind) }) });
      const alert = screen.getByRole("alert").textContent ?? "";
      for (const fragment of FAILURE_FRAGMENTS[kind]) expect(alert).toContain(fragment);
      // 실패했는데 "받고 있습니다"가 남으면 기다리면 되는 줄 안다.
      expect(screen.queryByText(/실거래를 받고 있습니다/)).toBeNull();
    });

  it("실거래 한도에 닿았으면 실거래 출처의 하루 한도이고 내일 다시 실행하면 이어 받는다고 말한다", () => {
    renderPicker({ complexes: complexesWith({ trades: failedTrades("rate_limited") }) });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("실거래 출처의 하루 호출 한도에 닿았습니다");
    expect(alert).toContain("내일 다시 실행");
  });

  it("종류마다 다른 말을 한다 — 인증 실패에 한도 문구가 섞이지 않는다", () => {
    renderPicker({ complexes: complexesWith({ trades: failedTrades("auth") }) });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).not.toContain(FAILURE_FRAGMENTS.rate_limited[0]);
    expect(alert).not.toContain(FAILURE_FRAGMENTS.network[0]);
  });

  it("실패가 없으면 경고가 없다", () => {
    renderPicker();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
