/**
 * 원금 칸의 쉼표 (T111) — 006 FR-053, SC-018, ui-wireframes W3. 반복 2026-10-03.
 *
 * 칸에는 `10,000,000`이 보이고, 화면 상태·요청·이력에는 `10000000`이 간다. 쉼표가 요청에 섞이면 서버가
 * 400을 내고, 이력에 섞이면 그 항목을 다시 실행할 때마다 거절된다 — 둘 다 사용자는 원인을 모른다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SimulationForm, type FormValues } from "@/components/stock/SimulationForm";
import { apiClient } from "@/lib/apiClient";
import type { SimulationResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";
// 012 승인 2026-10-07 — 012부터 이력은 로컬 DB에 있다. 브라우저 lib 대신 이력 대역에서 읽는다(research R12-12).
import { historyStub } from "./support/historyStub";

const VALUES: FormValues = {
  start: "2021-08-02", principal: "10000000", principalCurrency: "KRW", reinvest: true,
};

/** 부모가 상태를 들고 있는 실제 사용 모양. 값이 다시 그려져야 쉼표와 커서를 볼 수 있다. */
function Harness({ initial, onChange }: {
  initial: FormValues;
  onChange: (next: FormValues) => void;
}) {
  const [values, setValues] = useState(initial);
  return (
    <SimulationForm values={values} disabled={false} limit="2026-10-01" stockCurrency="KRW"
      onChange={(next) => { setValues(next); onChange(next); }} onSubmit={vi.fn()} />
  );
}

const principalBox = () =>
  screen.getByRole("textbox", { name: "투자 원금" }) as HTMLInputElement;

describe("원금 칸", () => {
  it("3자리마다 쉼표로 보인다", () => {
    render(<Harness initial={VALUES} onChange={vi.fn()} />);
    expect(principalBox().value).toBe("10,000,000");
  });

  it("치는 대로 쉼표가 붙고, 바깥으로는 쉼표 없는 값을 준다", async () => {
    const onChange = vi.fn();
    render(<Harness initial={{ ...VALUES, principal: "" }} onChange={onChange} />);
    await userEvent.type(principalBox(), "1234567");
    expect(principalBox().value).toBe("1,234,567");
    expect(onChange).toHaveBeenLastCalledWith({ ...VALUES, principal: "1234567" });
  });

  it("쉼표가 든 값을 붙여 넣어도 쉼표 없는 값을 준다", () => {
    const onChange = vi.fn();
    render(<Harness initial={{ ...VALUES, principal: "" }} onChange={onChange} />);
    fireEvent.change(principalBox(), { target: { value: "1,000,000" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...VALUES, principal: "1000000" });
    expect(principalBox().value).toBe("1,000,000");
  });

  it("소수부는 그대로 둔다", () => {
    const onChange = vi.fn();
    render(<Harness initial={{ ...VALUES, principal: "" }} onChange={onChange} />);
    fireEvent.change(principalBox(), { target: { value: "1234.5" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...VALUES, principal: "1234.5" });
    expect(principalBox().value).toBe("1,234.5");
  });

  it("가운데 자리를 고쳐도 커서가 끝으로 튀지 않는다", async () => {
    render(<Harness initial={{ ...VALUES, principal: "1000000" }} onChange={vi.fn()} />);
    // "1,000,000"의 첫 숫자 뒤에 2를 넣는다 → "12,000,000", 커서는 "12" 뒤.
    await userEvent.type(principalBox(), "2", { initialSelectionStart: 1, initialSelectionEnd: 1 });
    expect(principalBox().value).toBe("12,000,000");
    expect(principalBox().selectionStart).toBe(2);
  });
});

const RESULT: SimulationResponse = {
  stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  condition: { start: "2021-08-02", principal: "10000000", principalCurrency: "KRW",
    reinvest: true, tradeFeeRate: "0", dividendTaxRate: "0" },
  summary: { principal: "10000000", profit: "0", returnRate: "0", asOf: "2026-10-01",
    isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

describe("요청과 이력에는 쉼표가 없다 (SC-018)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    useStockStore.getState().dispose();
    useStockStore.setState({
      input: { stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
        start: "2021-08-02", principal: "", principalCurrency: "KRW", reinvest: true },
      summary: null, collecting: null, error: null,
    });
  });

  it("칸에 친 원금이 쉼표 없이 요청되고 이력에 남는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation((() =>
      Promise.resolve(RESULT)) as typeof apiClient.get);
    function Wired() {
      const input = useStockStore((s) => s.input);
      return (
        <SimulationForm values={input} disabled={false} limit="2026-10-01" stockCurrency="KRW"
          onChange={(next) => useStockStore.getState().setInput(next)} onSubmit={vi.fn()} />
      );
    }
    render(<Wired />);
    await userEvent.type(principalBox(), "10000000");
    expect(principalBox().value).toBe("10,000,000");

    await useStockStore.getState().run();
    const table = get.mock.calls.map(([path]) => String(path))
      .find((path) => path.startsWith("/api/stocks/simulation?"));
    expect(table).toContain("principal=10000000");
    expect(table).not.toMatch(/principal=[^&]*%2C/);
    expect(historyStub.entries("stock")[0].principal).toBe("10000000"); // 012 승인 2026-10-07
  });
});
