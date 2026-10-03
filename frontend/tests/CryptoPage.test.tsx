/**
 * 가상자산 화면 (T028) — 007 FR-001, FR-009, FR-021, FR-022, ui-wireframes C1.
 *
 * 주식 화면과 같은 구성이되 **배당 재투자 칸이 없다**. 화면 머리에 일봉 기준(UTC 하루)을 밝히고, 시작일 상한은 **UTC 어제**다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import { utcYesterday } from "@/lib/startDate";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({
  subscribeCoinListProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

describe("가상자산 화면", () => {
  it("제목과 일봉 기준을 밝힌다", () => {
    render(<CryptoPage />);
    expect(screen.getByRole("heading", { name: "가상자산 투자 시뮬레이션" })).toBeInTheDocument();
    expect(screen.getByText(/일봉 기준: UTC 하루/)).toBeInTheDocument();
  });

  it("코인 검색 칸이 있고 배당 재투자 칸이 없다", () => {
    render(<CryptoPage />);
    expect(screen.getByRole("searchbox", { name: "코인 검색" })).toBeInTheDocument();
    expect(screen.queryByText("배당 재투자")).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("시작일 상한은 UTC 어제다", () => {
    render(<CryptoPage />);
    expect(screen.getByLabelText("시작일")).toHaveAttribute("max", utcYesterday());
  });

  it("코인을 고르기 전에는 실행할 수 없다", () => {
    render(<CryptoPage />);
    expect(screen.getByRole("button", { name: "시뮬레이션" })).toBeDisabled();
  });
});
