/**
 * 부동산 시뮬레이션 조건 입력 (T034) — 009 FR-002, FR-005, FR-006, FR-007, FR-023, ui-wireframes E1·E3.
 *
 * - 매입일은 다른 자산군과 같다 — 달력, `‹ ›` 한 달, `« »` 1년(006 `StartDateInput`). **상한은 오늘(한국 시간)**, **하한은 고른 평형의
 *   `startableFrom`**(달력의 `min`)
 * - 매입일이 시작 가능 날짜보다 이르면 **실행 전에** 그 사실·날짜·근거를 보이고 옮기기 수단을 준다 — 조용히 옮기지 않는다(FR-005).
 *   근거가 첫 거래 달(`first_trade`)이면 "이 단지의 30평대(국평) 거래는 2020-02부터", 세법 표의 첫 날(`tax_rules`)이면 "세법 표는
 *   2006-01-01부터 있습니다(첫 거래는 2005-12)"(E3)
 * - 매입가는 **선택** 칸이다 — 비우면 그 달 시세. 3자리 쉼표, 단위 "원". 쉼표는 표시에만 있고 값은 숫자 문자열이다. 0은 거절(FR-006)
 * - 실행의 거절(409, E3) — `no_price_at_purchase`는 사유와 함께 **매입가 칸으로 초점을 옮긴다**, `no_trades_in_area`, `tax_rule_not_covered`는
 *   세목과 날짜(가까운 해로 대신하지 않는다, FR-023), `region_retired`는 개편 사실과 "지역에서 다시 골라 실행"(FR-002). 모두 `role="alert"`
 * - 통화 칸이 없다(FR-007)
 *
 * ## 이 테스트가 전제하는 모듈 (T039가 따른다)
 *
 * `@/components/realestate/RealEstateSimulationForm` — `export function RealEstateSimulationForm(props)`
 * - `values: { buyDate: string; buyPrice: string }` — `buyPrice`는 쉼표 없는 숫자 문자열, 비었으면 그 달 시세
 * - `disabled: boolean`, `limit: string`(오늘, 한국 시간), `areaLabel: string | null`(고른 평형의 이름 — 안내 문구에 쓴다)
 * - `startBound: { startableFrom: string; basis: "first_trade" | "tax_rules"; firstMonth: string | null } | null` — 고른 평형의 시작 가능
 *   날짜와 근거(실행 전에는 평형 구분에서, 실행 뒤에는 409 `before_first_trade`에서)
 * - `rejection: RealEstateRejection | null` — `@/stores/realEstateStore`의 형식:
 *   `{ kind: "no_price_at_purchase"; month } | { kind: "no_trades_in_area" } | { kind: "tax_rule_not_covered"; tax; date } |
 *   { kind: "region_retired"; lawdCd }`
 * - `onChange: (next: { buyDate; buyPrice }) => void`, `onSubmit: () => void`
 * - 매입일 칸의 `label`은 "매입일", 매입가 칸의 `label`은 "매입가"로 시작한다. 실행 버튼은 "시뮬레이션"
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { RealEstateSimulationForm } from "@/components/realestate/RealEstateSimulationForm";

type Props = ComponentProps<typeof RealEstateSimulationForm>;

const LIMIT = "2026-10-05";
const FIRST_TRADE: Props["startBound"] = { startableFrom: "2020-02-01", basis: "first_trade", firstMonth: "2020-02" };
const TAX_RULES: Props["startBound"] = { startableFrom: "2006-01-01", basis: "tax_rules", firstMonth: "2005-12" };

function renderForm(over: Partial<Props> = {}) {
  const onChange = vi.fn();
  const onSubmit = vi.fn();
  render(
    <RealEstateSimulationForm
      values={{ buyDate: "2021-03-15", buyPrice: "" }}
      disabled={false}
      limit={LIMIT}
      areaLabel="30평대(국평)"
      startBound={FIRST_TRADE}
      rejection={null}
      onChange={onChange}
      onSubmit={onSubmit}
      {...over}
    />,
  );
  return { onChange, onSubmit };
}

const buyDate = () => screen.getByLabelText("매입일");
const buyPrice = () => screen.getByLabelText(/^매입가/);
const submit = () => screen.getByRole("button", { name: "시뮬레이션" });

describe("매입일", () => {
  it("달력의 상한은 오늘, 하한은 고른 평형의 시작 가능 날짜다", () => {
    renderForm();
    expect(buyDate()).toHaveAttribute("type", "date");
    expect(buyDate()).toHaveAttribute("max", LIMIT);
    expect(buyDate()).toHaveAttribute("min", "2020-02-01");
  });

  it("평형을 고르기 전에는 하한이 없다", () => {
    renderForm({ startBound: null });
    expect(buyDate()).not.toHaveAttribute("min");
  });

  it("한 달·1년 이동 — 매입가는 그대로 둔다", () => {
    const { onChange } = renderForm({ values: { buyDate: "2021-03-15", buyPrice: "2000000000" } });
    fireEvent.click(screen.getByRole("button", { name: "한 달 뒤" }));
    expect(onChange).toHaveBeenLastCalledWith({ buyDate: "2021-04-15", buyPrice: "2000000000" });
    fireEvent.click(screen.getByRole("button", { name: "1년 전" }));
    expect(onChange).toHaveBeenLastCalledWith({ buyDate: "2020-03-15", buyPrice: "2000000000" });
  });

  it("오늘의 달을 넘어가는 이동은 누를 수 없다", () => {
    renderForm({ values: { buyDate: "2026-10-01", buyPrice: "" } });
    expect(screen.getByRole("button", { name: "한 달 뒤" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "1년 뒤" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "한 달 전" })).toBeEnabled();
  });

  it("오늘보다 뒤면 사유를 보이고 실행할 수 없다", () => {
    renderForm({ values: { buyDate: "2026-10-06", buyPrice: "" } });
    expect(screen.getByRole("alert").textContent).toContain(LIMIT);
    expect(submit()).toBeDisabled();
  });

  it("오늘은 고를 수 있다", () => {
    renderForm({ values: { buyDate: LIMIT, buyPrice: "" } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(submit()).toBeEnabled();
  });
});

describe("시작 가능 날짜보다 이를 때 (FR-005, E3)", () => {
  it("첫 거래 달이 근거면 그 달을 밝히고 옮기기 수단을 준다 — 몰래 옮기지 않는다", () => {
    const { onChange } = renderForm({ values: { buyDate: "2018-01-01", buyPrice: "" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("30평대(국평) 거래는 2020-02부터 있습니다");
    expect(alert).toContain("2020-02-01 이후");
    expect(onChange).not.toHaveBeenCalled();
    expect(submit()).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "2020-02로 옮기기" }));
    expect(onChange).toHaveBeenCalledWith({ buyDate: "2020-02-01", buyPrice: "" });
  });

  it("세법 표가 근거면 세법 표의 첫 날과 첫 거래 달을 밝힌다", () => {
    const { onChange } = renderForm({ startBound: TAX_RULES, values: { buyDate: "2005-12-26", buyPrice: "" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("세법 표는 2006-01-01부터 있습니다");
    expect(alert).toContain("첫 거래는 2005-12");
    expect(alert).not.toContain("거래는 2006-01부터");
    fireEvent.click(screen.getByRole("button", { name: "2006-01로 옮기기" }));
    expect(onChange).toHaveBeenCalledWith({ buyDate: "2006-01-01", buyPrice: "" });
  });

  it("시작 가능 날짜부터는 알리지 않는다", () => {
    renderForm({ values: { buyDate: "2020-02-01", buyPrice: "" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("매입가 (FR-006)", () => {
  it("선택 칸이다 — 비우면 그 달 시세라고 알리고 실행할 수 있다", () => {
    renderForm();
    expect(buyPrice()).toHaveValue("");
    expect(screen.getByText(/비우면 그 달 시세/)).toBeInTheDocument();
    expect(submit()).toBeEnabled();
  });

  it("3자리마다 쉼표로 보이고 단위는 원이다", () => {
    renderForm({ values: { buyDate: "2021-03-15", buyPrice: "2023166667" } });
    expect(buyPrice()).toHaveValue("2,023,166,667");
    expect(screen.getByText("원")).toBeInTheDocument();
  });

  it("쉼표·글자는 값에 들어가지 않는다 — 숫자 문자열로 알린다", () => {
    const { onChange } = renderForm();
    fireEvent.change(buyPrice(), { target: { value: "1,500,000,000" } });
    expect(onChange).toHaveBeenLastCalledWith({ buyDate: "2021-03-15", buyPrice: "1500000000" });
    fireEvent.change(buyPrice(), { target: { value: "-12a3" } });
    expect(onChange).toHaveBeenLastCalledWith({ buyDate: "2021-03-15", buyPrice: "123" });
  });

  it("원 미만은 없다 — 소수점 뒤를 버린다", () => {
    const { onChange } = renderForm();
    fireEvent.change(buyPrice(), { target: { value: "1500.7" } });
    expect(onChange).toHaveBeenLastCalledWith({ buyDate: "2021-03-15", buyPrice: "1500" });
  });

  it("0이면 거절하고 실행할 수 없다", () => {
    renderForm({ values: { buyDate: "2021-03-15", buyPrice: "0" } });
    expect(screen.getByRole("alert").textContent).toContain("매입가");
    expect(submit()).toBeDisabled();
  });

  it("통화 칸이 없다(FR-007)", () => {
    renderForm();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});

describe("실행", () => {
  it("누르면 실행을 알린다", async () => {
    const { onSubmit } = renderForm();
    await userEvent.click(submit());
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("실행 중에는 누를 수 없다", () => {
    renderForm({ disabled: true });
    expect(submit()).toBeDisabled();
  });
});

describe("실행의 거절 (409, E3)", () => {
  it("매입 달 시세가 없으면 그 달과 할 일을 말하고 매입가 칸으로 초점을 옮긴다", () => {
    renderForm({ rejection: { kind: "no_price_at_purchase", month: "2019-05" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("2019-05");
    expect(alert).toContain("30평대(국평) 시세가 없습니다");
    expect(alert).toContain("매입가를 넣으면 계산할 수 있습니다");
    expect(buyPrice()).toHaveFocus();
  });

  it("그 평형의 거래가 없으면 그 사실", () => {
    renderForm({ rejection: { kind: "no_trades_in_area" } });
    expect(screen.getByRole("alert").textContent).toContain("이 단지에 30평대(국평) 거래가 없습니다");
  });

  it("세법 표가 덮지 않으면 세목과 날짜를 밝힌다", () => {
    renderForm({ rejection: { kind: "tax_rule_not_covered", tax: "property", date: "2021-06-01" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("재산세");
    expect(alert).toContain("2021-06-01");
  });

  it("종부세면 종부세라고 밝힌다", () => {
    renderForm({ rejection: { kind: "tax_rule_not_covered", tax: "comprehensive", date: "2022-06-01" } });
    expect(screen.getByRole("alert").textContent).toMatch(/종부세|종합부동산세/);
  });

  it("시·군·구가 개편으로 사라졌으면 그 사실과 지역에서 다시 골라 실행하라고 말한다", () => {
    renderForm({ rejection: { kind: "region_retired", lawdCd: "42110" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("행정구역 개편");
    expect(alert).toContain("지역에서 다시 골라 실행");
    // 조용히 "거래 없음"으로 보이지 않는다.
    expect(alert).not.toContain("거래가 없습니다");
  });

  it("거절이 없으면 경고가 없다", () => {
    renderForm();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(buyPrice()).not.toHaveFocus();
  });
});
