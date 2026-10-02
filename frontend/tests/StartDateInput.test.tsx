/**
 * 시작일 입력 (T057) — 006 FR-001, FR-002, FR-004, FR-005, ui-wireframes W1·W1a.
 *
 * **시작일을 사용자 몰래 옮기지 않는다**(005 FR-005). 상장일보다 이르면 실행 전에 알리고, 옮기기는
 * 눌러야만 일어난다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StartDateInput } from "@/components/stock/StartDateInput";

const LIMIT = "2026-10-01";

function setup(value: string, extra: Partial<Parameters<typeof StartDateInput>[0]> = {}) {
  const onChange = vi.fn();
  render(<StartDateInput value={value} limit={LIMIT} listedOn={null} startable={null}
    onChange={onChange} {...extra} />);
  return onChange;
}

describe("이동 버튼 (W1)", () => {
  it("보조 기술이 읽는 이름을 갖는다", () => {
    setup("2020-01-01");
    for (const name of ["1년 전", "한 달 전", "한 달 뒤", "1년 뒤"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("누르면 옮긴 날짜를 알린다", () => {
    const onChange = setup("2020-01-31");
    fireEvent.click(screen.getByRole("button", { name: "한 달 뒤" }));
    expect(onChange).toHaveBeenLastCalledWith("2020-02-29");
    fireEvent.click(screen.getByRole("button", { name: "1년 전" }));
    expect(onChange).toHaveBeenLastCalledWith("2019-01-31");
  });

  it("어제의 달을 넘어가는 버튼은 누를 수 없다", () => {
    setup("2026-10-01");
    expect(screen.getByRole("button", { name: "한 달 뒤" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "1년 뒤" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "한 달 전" })).toBeEnabled();
  });

  it("직접 입력할 수 있다", () => {
    const onChange = setup("2020-01-01");
    fireEvent.change(screen.getByLabelText("시작일"), { target: { value: "2018-05-15" } });
    expect(onChange).toHaveBeenLastCalledWith("2018-05-15");
  });
});

describe("미래 날짜 (FR-004)", () => {
  it("어제보다 뒤면 사유를 보인다", () => {
    setup("2026-10-05");
    expect(screen.getByRole("alert").textContent).toMatch(/2026-10-01/);
  });

  it("어제까지는 사유를 보이지 않는다", () => {
    setup("2026-10-01");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("상장일보다 이를 때 (W1a, FR-005)", () => {
  it("실행 전에 알리고 옮기기 수단을 준다", () => {
    const onChange = setup("2020-01-01", { listedOn: "2021-05-03" });
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("2021-05-03");
    expect(onChange).not.toHaveBeenCalled();                 // 몰래 옮기지 않는다
    fireEvent.click(screen.getByRole("button", { name: "2021-05로 옮기기" }));
    expect(onChange).toHaveBeenCalledWith("2021-05-03");
  });

  it("상장일 이후면 알리지 않는다", () => {
    setup("2021-05-03", { listedOn: "2021-05-03" });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("실행 뒤 시세 시작일을 받으면 같은 모양으로 보인다", () => {
    // FR-005a — basis: price_start. 상장일은 하한일 뿐이라 시세가 더 늦게 시작할 수 있다.
    const onChange = setup("2021-05-10", {
      listedOn: "2021-05-03",
      startable: { startableFrom: "2021-07-01", basis: "price_start",
        message: "2021-07-01부터 시세가 있습니다. 그 이전은 계산할 수 없습니다." },
    });
    expect(screen.getByRole("alert").textContent).toContain("2021-07-01");
    fireEvent.click(screen.getByRole("button", { name: "2021-07로 옮기기" }));
    expect(onChange).toHaveBeenCalledWith("2021-07-01");
  });
});
