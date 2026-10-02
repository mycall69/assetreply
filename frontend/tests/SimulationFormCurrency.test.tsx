/**
 * 원금 통화 선택 (T077) — 006 FR-050b, FR-050d, SC-011a, ui-wireframes W3.
 *
 * **원금 통화를 몰래 바꾸지 않는다.** 원금 통화만 원화로 바꾸고 금액을 그대로 두면 1,000 USD가
 * 1,000원이 된다 — 결과는 정상으로 보이는데 원금이 1,300분의 1로 줄어 있다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimulationForm, type FormValues } from "@/components/stock/SimulationForm";
import { allowedPrincipals } from "@/lib/principalCurrency";

const VALUES: FormValues = {
  start: "2021-08-02", principal: "1000", principalCurrency: "USD", reinvest: true,
};

function setup(stockCurrency: string | null, values: FormValues = VALUES) {
  const onChange = vi.fn();
  const onSubmit = vi.fn();
  render(<SimulationForm values={values} disabled={false} limit="2026-10-01"
    stockCurrency={stockCurrency} onChange={onChange} onSubmit={onSubmit} />);
  return { onChange, onSubmit };
}

const options = () =>
  screen.getAllByRole("option").filter((o) => !(o as HTMLOptionElement).disabled)
    .map((o) => o.textContent);

describe("허용 조합", () => {
  it.each([
    ["KRW", ["KRW"]],
    ["USD", ["KRW", "USD"]],
    ["JPY", ["KRW", "JPY"]],
    [null, ["KRW"]],
  ])("종목 통화 %s → %j", (currency, expected) => {
    expect(allowedPrincipals(currency)).toEqual(expected);
  });

  it("선택지는 KRW와 종목 통화뿐이고 EUR이 없다", () => {
    // FR-050d — 유로로 거래되는 지원 시장이 없다. 남겨 두면 고른 뒤 매번 거절당한다.
    setup("USD");
    expect(options()).toEqual(["KRW", "USD"]);
    expect(screen.queryByRole("option", { name: "EUR" })).toBeNull();
  });
});

describe("종목을 바꿔 허용되지 않게 되면 (FR-050b)", () => {
  it("값을 바꾸지 않고 다시 고르라고 하며 실행을 막는다", () => {
    // USD로 미국 종목을 보다가 국내 종목으로 바꿨다.
    const { onChange } = setup("KRW");
    expect(onChange).not.toHaveBeenCalled();
    expect((screen.getByLabelText("통화") as HTMLSelectElement).value).toBe("USD");
    expect(screen.getByRole("alert").textContent).toMatch(/다시 고르세요/);
    expect(screen.getByRole("alert").textContent).toMatch(/원화 원금만/);
    expect(screen.getByRole("button", { name: "시뮬레이션" })).toBeDisabled();
  });

  it("허용되는 통화를 고르면 풀린다", () => {
    const { onChange } = setup("KRW");
    fireEvent.change(screen.getByLabelText("통화"), { target: { value: "KRW" } });
    expect(onChange).toHaveBeenCalledWith({ ...VALUES, principalCurrency: "KRW" });
  });

  it("허용되면 안내가 없다", () => {
    setup("USD");
    expect(screen.queryByText(/다시 고르세요/)).toBeNull();
    expect(screen.getByRole("button", { name: "시뮬레이션" })).toBeEnabled();
  });
});
