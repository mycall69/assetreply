/**
 * 예금 화면 (T016) — 008 FR-001~FR-005, FR-035, ui-wireframes D1·D3·D8.
 *
 * 주식·가상자산과 같은 구성이되 **종목 검색 대신 투자처 라디오 버튼 다섯**이고, 원금은 **원화만**이다 — 통화 칸·재투자 칸이 없다.
 * 화면 아래에 출처(ECOS)를 밝힌다(약관 제7조 ②, research R8-2).
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DepositPage from "@/app/deposit/page";
import { apiClient } from "@/lib/apiClient";
import { kstToday } from "@/lib/startDate";
import { useDepositStore } from "@/stores/depositStore";
import { COLLECTING, INSTITUTIONS, RESULT } from "./support/depositFixtures";

vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(apiClient, "get").mockResolvedValue(INSTITUTIONS);
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-01", principal: "" },
    rows: [], summary: null, condition: null, collecting: null, progress: null, error: null,
    startable: null, loading: false,
  });
  useDepositStore.setState({ refreshIfRan: async () => undefined });
});

describe("예금 화면", () => {
  it("제목과 설명", () => {
    render(<DepositPage />);
    expect(screen.getByRole("heading", { name: "예금 투자 시뮬레이션" })).toBeInTheDocument();
    expect(screen.getByText(/1년 만기 정기예금에 가입하고 만기마다 세후 이자를 더해 재예치한 성과/))
      .toBeInTheDocument();
  });

  it("투자처는 라디오 다섯이고 기본은 시중은행이다", () => {
    render(<DepositPage />);
    const group = screen.getByRole("group", { name: "투자처" });
    // 011 — 상품(정기예금·정기 적금) 라디오가 따로 있어 투자처 묶음 안에서만 센다(사용자 승인 2026-10-06 — 기대값은 그대로)
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => r.getAttribute("aria-label") ?? r.closest("label")?.textContent))
      .toEqual(["시중은행", "저축은행", "신협", "상호금융", "새마을금고"]);
    expect(screen.getByRole("radio", { name: "시중은행" })).toBeChecked();
    expect(group).toBeInTheDocument();
  });

  it("통화 칸과 재투자 칸이 없고 원금 단위는 원이다", () => {
    render(<DepositPage />);
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.getByText("원")).toBeInTheDocument();
  });

  it("시작일 상한은 오늘(한국 시간)이다", () => {
    render(<DepositPage />);
    expect(screen.getByLabelText("시작일")).toHaveAttribute("max", kstToday());
  });

  it("출처를 밝힌다", () => {
    render(<DepositPage />);
    expect(screen.getByText(/출처: 한국은행 경제통계시스템\(ECOS\)/)).toBeInTheDocument();
  });

  it("수집 중이면 받은 달 / 받을 달을 개월로 보인다", () => {
    useDepositStore.setState({ collecting: COLLECTING, progress: { jobId: 3, status: "running",
      institution: "commercial_bank", monthsDone: 0, monthsTotal: 82, missingFrom: "2020-01",
      missingThrough: "2026-10" } });
    render(<DepositPage />);
    expect(screen.getByText("시중은행의 금리를 받고 있습니다")).toBeInTheDocument();
    expect(screen.getByText("0 / 82개월")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "82");
  });

  it("보드는 원화 기호가 숫자 앞이고 기준 줄에 투자처·세율·지금 회차를 늘 보인다(FR-035)", () => {
    useDepositStore.setState({ rows: RESULT.rows, summary: RESULT.summary, condition: RESULT.condition });
    render(<DepositPage />);
    expect(screen.getByText("₩10,000,000")).toBeInTheDocument();
    expect(screen.getByText("₩1,557,207")).toBeInTheDocument();
    const basis = screen.getByText(/KRW 기준/).closest("p")?.textContent ?? "";
    expect(basis).toContain("시중은행");
    expect(basis).toContain("세율 15.4%");
    expect(basis).toContain("지금 회차 2026-01-15 가입 · 2.84% · 만기 2027-01-15");
  });
});
