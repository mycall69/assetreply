/**
 * 기록 목록 검증 (T055) — FR-021, FR-023, ui-wireframes W6.
 *
 * **`고시 없음`과 `구간 실패`를 다른 문구로 쓰는 것이 FR-021의 시각적 귀결이다.**
 * 휴일이라 값이 없는 것과 수집이 실패한 것을 같게 보여주면, 나중에 시계열 공백의
 * 원인을 되짚을 때 기록이 아무 도움이 되지 않는다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EventList } from "@/components/collection/EventList";
import { IncompleteRecordNotice } from "@/components/collection/IncompleteRecordNotice";
import type { CollectionEventKind, CollectionEventRow } from "@/lib/types";

function row(kind: CollectionEventKind): CollectionEventRow {
  return {
    jobId: 1, currency: "USD", kind,
    chunkFrom: "2020-01-01", chunkTo: "2020-12-30",
    rowsStored: kind === "chunk_stored" ? 261 : null,
    detail: null, occurredAt: "2026-09-24T10:31:02",
  };
}

describe("결측과 실패 구별 (FR-021)", () => {
  it("고시 없음으로 표기한다", () => {
    render(<EventList events={[row("chunk_empty")]} jobsKept={20} />);
    expect(screen.getByText("고시 없음")).toBeTruthy();
  });

  it("구간 실패로 표기한다", () => {
    render(<EventList events={[row("chunk_failed")]} jobsKept={20} />);
    expect(screen.getByText("구간 실패")).toBeTruthy();
  });

  it("두 문구가 다르다", () => {
    render(<EventList events={[row("chunk_empty"), row("chunk_failed")]} jobsKept={20} />);
    expect(screen.getByText("고시 없음")).toBeTruthy();
    expect(screen.getByText("구간 실패")).toBeTruthy();
  });
});

describe("표기", () => {
  it("아홉 종류를 모두 표기한다", () => {
    const kinds: CollectionEventKind[] = [
      "job_started", "chunk_requested", "chunk_stored", "chunk_empty",
      "chunk_failed", "retry", "rate_limited", "job_finished", "log_sink_failed",
    ];
    render(<EventList events={kinds.map(row)} jobsKept={20} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(9);
  });

  it("저장 건수를 보여준다", () => {
    render(<EventList events={[row("chunk_stored")]} jobsKept={20} />);
    expect(screen.getByText("261건")).toBeTruthy();
  });

  it("비어 있으면 안내한다", () => {
    render(<EventList events={[]} jobsKept={20} />);
    expect(screen.getByText(/아직 기록이 없습니다/)).toBeTruthy();
  });
});

describe("보관 범위 안내 (FR-023)", () => {
  it("오래된 기록이 없는 이유를 설명한다", () => {
    render(<EventList events={[row("chunk_stored")]} jobsKept={20} />);
    expect(screen.getByText(/최근 20개 작업의 기록만 보관합니다/)).toBeTruthy();
  });
});

describe("기록 불완전 경고 (FR-018b)", () => {
  it("누락이 있으면 알린다", () => {
    render(<IncompleteRecordNotice dropped={3} />);
    expect(screen.getByText(/기록 3건이 저장되지 않았습니다/)).toBeTruthy();
  });

  it("수집은 정상임을 함께 알린다", () => {
    // 경고만 보면 사용자가 데이터를 의심한다.
    render(<IncompleteRecordNotice dropped={3} />);
    expect(screen.getByText(/수집 자체는 정상입니다/)).toBeTruthy();
  });

  it("누락이 없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<IncompleteRecordNotice dropped={0} />);
    expect(container.firstChild).toBeNull();
  });
});
