/**
 * 실패한 시·군·구에서 단지를 고르면 화면에 새 수집의 진행이 보인다 (T054 실측 결함) — 009 FR-011, FR-014, ui-wireframes E2·E9.
 *
 * 마지막 실거래 작업이 하루 한도로 실패한 송파구에서 헬리오시티를 고르면 평형 요청이 202다(서버가 새 작업을 시작했다). 고치기 전에는 진행
 * 줄이 없고 지난 실패 경고가 남아, 수집이 이어지는데도 화면은 막힌 것처럼 보였다. 기대: 곧바로 "송파구의 실거래를 받고 있습니다 | 받은 달 /
 * 받을 달개월" 줄이 보이고 지난 실패 경고가 사라진다. 진행이 오면 숫자가 바뀐다.
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RealEstatePage from "@/app/realestate/page";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  AREAS_COLLECTING,
  GARAK,
  HELIO_ID,
  SEOUL,
  SEOUL_SGGS,
  SIDOS,
  SONGPA,
  SONGPA_UMDS,
  complexesWith,
  failedTrades,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";
import { resetSimulation } from "./support/realEstateSimulationFixtures";

const progress = vi.hoisted(() => ({
  subs: [] as { jobId: number; handlers: RealEstateProgressHandlers; active: boolean }[],
}));
vi.mock("@/lib/realEstateProgressStream", () => ({
  subscribeRealEstateProgress: (jobId: number, handlers: RealEstateProgressHandlers) => {
    const sub = { jobId, handlers, active: true };
    progress.subs.push(sub);
    return () => {
      sub.active = false;
    };
  },
}));

function fire(jobId: number, event: (h: RealEstateProgressHandlers) => void): void {
  for (const s of progress.subs.filter((x) => x.jobId === jobId && x.active)) event(s.handlers);
}

const RESUMED = { ...AREAS_COLLECTING, jobId: 15, monthsDone: 120, monthsTotal: 250,
  progressUrl: "/api/realestate/progress?jobId=15" };
const LIMIT_TEXT = "실거래 출처의 하루 호출 한도에 닿았습니다";

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
  resetSimulation();
  progress.subs = [];
  useRealEstateStore.setState({
    regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
    selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: null, area: null },
    complexes: complexesWith({ trades: failedTrades("rate_limited", "하루 한도") }),
  });
  routeRealEstate((path) =>
    splitPath(path).base === `/api/realestate/complexes/${HELIO_ID}/areas` ? RESUMED : realEstateRoutes(path));
});

describe("실패한 시·군·구에서 단지를 고르면", () => {
  it("지난 실패 경고 대신 새 수집의 진행 줄이 보인다", async () => {
    render(<RealEstatePage />);
    // 고르기 전에는 지난 실패가 보인다(FR-014 — 다시 열어도 사유가 보인다).
    expect(screen.getByRole("alert").textContent).toContain(LIMIT_TEXT);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "단지" }), "헬리오시티 · 2018년 입주 · 9,510세대");

    expect(await screen.findByText(/송파구의? 실거래를 받고 있습니다/)).toBeInTheDocument();
    expect(screen.getByText(/120 \/ 250개월/)).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(LIMIT_TEXT))).toBeNull();
    expect(screen.getByText(/실거래를 받은 뒤 고를 수 있습니다/)).toBeInTheDocument();
  });

  it("진행이 오면 받은 달이 바뀐다", async () => {
    render(<RealEstatePage />);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "단지" }), "헬리오시티 · 2018년 입주 · 9,510세대");
    await screen.findByText(/송파구의? 실거래를 받고 있습니다/);
    act(() => fire(15, (h) => h.onSnapshot({ jobId: 15, kind: "trade", target: "11710", status: "running",
      done: 131, total: 250 })));
    expect(screen.getByText(/131 \/ 250개월/)).toBeInTheDocument();
  });
});
