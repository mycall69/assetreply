/**
 * 설정 — 투자 비교 (014 반복 2026-10-13 T214) — spec FR-044, SC-027, contracts A18, ui-wireframes D19.
 *
 * - 설정 화면의 새 절 "투자 비교"는 부동산 두 절 뒤, "최근 시뮬레이션 이력" 앞이다(이력이 맨 아래 — 012 F7 그대로)
 * - 칸은 "최대 대상 수" 정수 하나(처음 값은 서버 값 — 행이 없으면 20)이고, 범위·기본·안내 숫자는 서버 값이다
 * - 정수 2~100이 아니면 요청 없이 칸 오류다. 서버가 거절하면 그 메시지이고, 실패해도 칸 값은 사용자가 친 그대로다
 * - 다른 절과 상태를 나누지 않는다 — 한쪽 실패가 다른 쪽을 가리면 무엇이 저장됐는지 알 수 없다(005와 같은 까닭)
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { CompareSettingsSection } from "@/components/settings/CompareSettingsSection";
import { apiClient } from "@/lib/apiClient";
import { compareSettingsStub } from "./support/compareSettingsStub";

const SECTION = "투자 비교";
const section = () => screen.getByRole("heading", { level: 2, name: SECTION }).parentElement as HTMLElement;
const box = () => within(section()).getByLabelText("최대 대상 수");
const puts = () => compareSettingsStub.calls().filter((c) => c.method === "PUT");

async function typeAndSave(typed: string) {
  await userEvent.clear(box());
  if (typed !== "") await userEvent.type(box(), typed);
  await userEvent.click(within(section()).getByRole("button", { name: "저장" }));
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("투자 비교 절", () => {
  it("처음 값은 서버 값이고 안내는 기본·범위·예금이다", async () => {
    render(<CompareSettingsSection />);
    expect(await within(section()).findByLabelText("최대 대상 수")).toHaveValue("20");
    expect(within(section()).getByText("ⓘ 기본 20개 · 2~100개 · 예금은 투자처가 다섯이라 5개까지")).toBeInTheDocument();
    expect(within(section()).getByText("개")).toBeInTheDocument();
  });

  it("저장된 값을 보인다", async () => {
    compareSettingsStub.set(45);
    render(<CompareSettingsSection />);
    expect(await within(section()).findByLabelText("최대 대상 수")).toHaveValue("45");
  });

  it("저장하면 정수를 보내고 알린다", async () => {
    render(<CompareSettingsSection />);
    await within(section()).findByLabelText("최대 대상 수");
    await typeAndSave("100");
    expect(await within(section()).findByText("저장했습니다. 투자 비교 화면을 다시 열면 새 한도로 더할 수 있습니다.")).toBeInTheDocument();
    expect(puts().map((c) => c.body)).toEqual([{ maxTargets: 100 }]);
    expect(compareSettingsStub.stored()).toBe(100);
    expect(box()).toHaveValue("100");
  });

  it.each(["1", "101", "20.5", "", "abc", "0"])("%s는 요청 없이 칸 오류이고 지금 값은 그대로다", async (typed) => {
    compareSettingsStub.set(30);
    render(<CompareSettingsSection />);
    await within(section()).findByLabelText("최대 대상 수");
    await typeAndSave(typed);
    expect(within(section()).getByRole("alert")).toHaveTextContent("2~100 사이의 정수여야 합니다");
    expect(puts()).toEqual([]);
    expect(compareSettingsStub.stored()).toBe(30);
    expect(box()).toHaveValue(typed);
  });

  it("서버가 실패하면 그 사실을 알리고 칸 값은 친 그대로다", async () => {
    render(<CompareSettingsSection />);
    await within(section()).findByLabelText("최대 대상 수");
    compareSettingsStub.fail("PUT");
    await typeAndSave("70");
    expect(await within(section()).findByRole("alert")).toHaveTextContent("대역이 실패를 만들었다");
    expect(box()).toHaveValue("70");
    expect(within(section()).queryByText(/저장했습니다/)).toBeNull();
  });

  it("읽지 못하면 알리고 칸을 보이지 않는다", async () => {
    compareSettingsStub.fail("GET");
    render(<CompareSettingsSection />);
    expect(await within(section()).findByRole("alert")).toHaveTextContent("대역이 실패를 만들었다");
    expect(within(section()).queryByLabelText("최대 대상 수")).toBeNull();
  });
});

describe("설정 화면", () => {
  function routeSettings() {
    return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/realestate/settings") return { holdingTaxBaseRatio: "0.600000", isDefault: true };
      if (path === "/api/realestate/settings/residence") return { residenceRatio: "0.500000", isDefault: true };
      if (path === "/api/deposit/settings") return { interestTaxRate: "0.154000", isDefault: true };
      if (path === "/api/crypto/settings") return { tradeFeeRate: "0.001000", isDefault: true };
      if (path === "/api/stocks/settings") {
        return { tradeFeeRate: "0.000150", dividendTaxRate: "0.154000", dividendTaxRateUs: "0.150000", isDefault: true };
      }
      throw new Error(`unexpected ${path}`);
    });
  }

  it("부동산 두 절 뒤, 최근 시뮬레이션 이력 앞이다", async () => {
    routeSettings();
    render(<SettingsPage />);
    await screen.findByRole("heading", { level: 2, name: SECTION });
    const names = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    const at = (name: string) => names.indexOf(name);
    expect(at(SECTION)).toBeGreaterThan(at("부동산 보유세 기준 비율"));
    expect(at(SECTION)).toBeGreaterThan(at("부동산 거주 기간 비율"));
    expect(at(SECTION)).toBe(at("최근 시뮬레이션 이력") - 1);
    expect(at("최근 시뮬레이션 이력")).toBe(names.length - 1);
  });

  it("다른 절의 실패와 섞이지 않는다", async () => {
    routeSettings();
    render(<SettingsPage />);
    expect(await within(section()).findByLabelText("최대 대상 수")).toHaveValue("20");
    expect(within(section()).queryByRole("alert")).toBeNull();
  });
});
