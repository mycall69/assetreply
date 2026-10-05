/**
 * 평형 고르기 (T020) — 009 FR-004, ui-wireframes E1·E2·접근성.
 *
 * - **라디오 일곱**을 `fieldset`·`legend`("평형")로 묶는다. 각 항목에 해제를 뺀 거래 수 — "30평대(국평) 301건"
 * - 거래가 0인 구분은 **비활성**과 글자 "거래 없음" — 색만으로 가르지 않는다. 고를 수 있으면 시세가 없는 구분을 실행한다
 * - "전용면적 경계"는 일곱 구분의 경계표를 펼친다(국민주택규모 85㎡로 30평대를 가른다)
 * - 고른 구분 아래 한 줄 — "30평대(국평) — 전용 70㎡ 이상 85㎡ 이하 · 2020-02부터"(경계와 첫 거래 달). 항목의 경계 줄을
 *   `aria-describedby`로 잇는다
 * - 실거래를 받기 전에는 거래 수를 모른다 — "실거래를 받은 뒤 고를 수 있습니다"(E2). 0건으로 보이면 거래가 없는 단지로 읽는다
 *
 * ## 이 테스트가 전제하는 모듈 (T026이 따른다)
 *
 * `@/components/realestate/AreaBucketPicker` — `export function AreaBucketPicker(props)`
 * - `areas: RealEstateAreasResponse | null` — 받기 전 `null`
 * - `value: RealEstateAreaKey | null`
 * - `onChange: (key: RealEstateAreaKey) => void`
 * - `waitingForTrades: boolean` — 그 시·군·구의 실거래를 아직 다 받지 않았다(수집 중·실패·평형 202). 안내를 보이고 고를 수 없다
 * - `fieldset`·`legend` "평형"은 단지를 고르기 전에도 늘 그린다(E1)
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { AreaBucketPicker } from "@/components/realestate/AreaBucketPicker";
import { HELIO_AREAS } from "./support/realEstateFixtures";

type Props = ComponentProps<typeof AreaBucketPicker>;

const BASE: Props = { areas: HELIO_AREAS, value: null, onChange: () => undefined, waitingForTrades: false };

function renderPicker(over: Partial<Props> = {}) {
  const onChange = vi.fn();
  render(<AreaBucketPicker {...BASE} onChange={onChange} {...over} />);
  return onChange;
}

/** E1의 경계표 — 구분 이름과 전용면적 범위. */
const BOUNDARIES: [string, string][] = [
  ["10평대", "50㎡ 미만"],
  ["20평대", "50㎡ 이상 70㎡ 미만"],
  ["30평대(국평)", "70㎡ 이상 85㎡ 이하"],
  ["30평대(대형)", "85㎡ 초과 105㎡ 미만"],
  ["40평대", "105㎡ 이상 135㎡ 미만"],
  ["50평대", "135㎡ 이상 165㎡ 미만"],
  ["60평대 이상", "165㎡ 이상"],
];

describe("평형 라디오", () => {
  it("fieldset과 legend로 묶인 라디오 일곱이다", () => {
    renderPicker();
    const group = screen.getByRole("group", { name: "평형" });
    expect(group.tagName).toBe("FIELDSET");
    expect(within(group).getAllByRole("radio").map((r) => r.getAttribute("value")))
      .toEqual(["10", "20", "30k", "30l", "40", "50", "60"]);
  });

  it("각 항목에 해제를 뺀 거래 수를 보인다", () => {
    renderPicker();
    expect(screen.getByRole("radio", { name: /^10평대\s*101건$/ })).toBeEnabled();
    expect(screen.getByRole("radio", { name: /^30평대\(국평\)\s*301건$/ })).toBeEnabled();
    expect(screen.getByRole("radio", { name: /^30평대\(대형\)\s*27건$/ })).toBeEnabled();
  });

  it("거래가 0인 구분은 비활성이고 글자로 거래 없음이라고 말한다", () => {
    renderPicker();
    expect(screen.getByRole("radio", { name: /^50평대\s*거래 없음$/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /^60평대 이상\s*거래 없음$/ })).toBeDisabled();
    // "0건"으로 보이면 비활성 이유를 숫자에서 읽어야 한다. ("30건"은 0건이 아니다.)
    expect(screen.queryByText(/(^|\D)0건/)).toBeNull();
  });

  it("누르면 그 구분의 키를 알린다", async () => {
    const onChange = renderPicker();
    await userEvent.click(screen.getByRole("radio", { name: /^20평대/ }));
    expect(onChange).toHaveBeenCalledWith("20");
  });

  it("거래 없는 구분은 눌러도 알리지 않는다", async () => {
    const onChange = renderPicker();
    await userEvent.click(screen.getByRole("radio", { name: /^50평대/ }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("고른 구분이 선택되어 있다", () => {
    renderPicker({ value: "30k" });
    expect(screen.getByRole("radio", { name: /^30평대\(국평\)/ })).toBeChecked();
    expect(screen.getAllByRole("radio").filter((r) => (r as HTMLInputElement).checked)).toHaveLength(1);
  });
});

describe("고른 구분의 경계와 첫 달", () => {
  const LINE = "30평대(국평) — 전용 70㎡ 이상 85㎡ 이하 · 2020-02부터";

  it("고른 구분 아래에 경계와 첫 거래 달을 한 줄로 보인다", () => {
    renderPicker({ value: "30k" });
    expect(screen.getByText(LINE)).toBeInTheDocument();
  });

  it("그 줄을 고른 항목의 aria-describedby로 잇는다", () => {
    renderPicker({ value: "30k" });
    expect(screen.getByRole("radio", { name: /^30평대\(국평\)/ })).toHaveAccessibleDescription(LINE);
  });

  it("고르지 않은 항목도 자기 경계를 설명으로 가진다", () => {
    renderPicker({ value: "30k" });
    expect(screen.getByRole("radio", { name: /^20평대/ }))
      .toHaveAccessibleDescription(/50㎡ 이상 70㎡ 미만/);
  });

  it("고르지 않았으면 그 줄이 없다", () => {
    renderPicker();
    expect(screen.queryByText(/— 전용/)).toBeNull();
  });
});

describe("전용면적 경계표", () => {
  it("처음에는 접혀 있고, 누르면 일곱 구분의 경계를 펼친다", async () => {
    renderPicker();
    const toggle = screen.getByRole("button", { name: /전용면적 경계/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table")).toBeNull();

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const rows = within(screen.getByRole("table")).getAllByRole("row").map((r) => r.textContent ?? "");
    // 머리 줄 + 일곱 구분.
    expect(rows).toHaveLength(8);
    for (const [label, range] of BOUNDARIES) {
      expect(rows.some((text) => text.includes(label) && text.includes(range))).toBe(true);
    }
  });

  it("다시 누르면 접는다", async () => {
    renderPicker();
    const toggle = screen.getByRole("button", { name: /전용면적 경계/ });
    await userEvent.click(toggle);
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("실거래를 받기 전", () => {
  it("평형 칸이 안내를 보이고 고를 수 있는 항목이 없다", () => {
    renderPicker({ areas: null, waitingForTrades: true });
    const group = screen.getByRole("group", { name: "평형" });
    expect(within(group).getByText(/실거래를 받은 뒤 고를 수 있습니다/)).toBeInTheDocument();
    const enabled = within(group).queryAllByRole("radio").filter((r) => !(r as HTMLInputElement).disabled);
    expect(enabled).toEqual([]);
    // 거래 수를 모르는데 "거래 없음"이라고 하면 거래가 없는 단지로 읽는다.
    expect(within(group).queryByText(/거래 없음/)).toBeNull();
  });

  it("받은 뒤에는 안내가 없다", () => {
    renderPicker();
    expect(screen.queryByText(/실거래를 받은 뒤 고를 수 있습니다/)).toBeNull();
  });
});
