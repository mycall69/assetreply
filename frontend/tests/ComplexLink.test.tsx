/**
 * 부동산 단지 이름 링크 (010 반복 3, T063) — FR-029, FR-026(물러남), data-model 8.2, ui-wireframes F5 보탬.
 *
 * - 링크는 **처음부터 있다** — 네이버 검색 주소(FR-026)로 시작하고, 단지 번호 경로가 `found`를 주면 Npay 부동산의 그 단지 화면이 된다
 * - 못 찾음·실패·요청 오류는 검색 그대로다 — 링크가 사라지거나 틀린 단지로 가지 않는다
 * - 같은 단지는 한 번만 묻는다(보드와 이력 행에 같은 단지가 여럿이어도) — 화면을 그릴 때마다 출처를 부르면 차단된다
 * - 새 탭·`noopener noreferrer`, 누름이 행으로 올라가지 않는 것은 반복 1의 `ExternalLink` 그대로
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComplexLink } from "@/components/realestate/ComplexLink";
import { apiClient } from "@/lib/apiClient";
import { complexSearchLink } from "@/lib/externalLinks";
import { resetNaverComplexLinks } from "@/lib/naverComplexLink";

const HELIO_URL = "https://fin.land.naver.com/complexes/111515";

function answer(status: "found" | "not_found" | "failed", url: string | null = null, reason: string | null = null) {
  return (path: string) => {
    const id = Number(/complexes\/(\d+)\/naver/.exec(path)?.[1]);
    return Promise.resolve({ complexId: id, status, url, reason } as never);
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetNaverComplexLinks();
});

describe("단지 이름 링크", () => {
  it("검색 주소로 시작하고 번호를 찾으면 Npay 부동산 단지 화면이 된다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(answer("found", HELIO_URL));
    render(<ComplexLink complexId={4} name="헬리오시티아파트" umdName="가락동" />);
    const first = screen.getByRole("link", { name: "헬리오시티아파트 네이버에서 단지 찾기" });
    expect(first).toHaveAttribute("href", complexSearchLink("헬리오시티아파트", "가락동"));
    const direct = await screen.findByRole("link", { name: "헬리오시티아파트 Npay 부동산에서 보기" });
    expect(direct).toHaveAttribute("href", HELIO_URL);
    expect(direct).toHaveAttribute("target", "_blank");
    expect(direct).toHaveAttribute("rel", "noopener noreferrer");
    expect(get).toHaveBeenCalledWith("/api/realestate/complexes/4/naver");
  });

  it.each([
    ["못 찾음", answer("not_found")],
    ["실패", answer("failed", null, "rate_limited")],
    ["요청 오류", () => Promise.reject(new Error("network"))],
  ])("%s이면 검색 주소 그대로다", async (_name, impl) => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(impl as never);
    render(<ComplexLink complexId={17} name="가락미륭아파트" umdName="가락동" />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    await Promise.resolve();
    const link = screen.getByRole("link", { name: "가락미륭아파트 네이버에서 단지 찾기" });
    expect(link).toHaveAttribute("href", complexSearchLink("가락미륭아파트", "가락동"));
  });

  it("같은 단지는 한 번만 묻는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(answer("found", HELIO_URL));
    render(<>
      <ComplexLink complexId={4} name="헬리오시티아파트" umdName="가락동" />
      <ComplexLink complexId={4} name="헬리오시티아파트" umdName={null} />
    </>);
    await waitFor(() => expect(screen.getAllByRole("link", { name: /Npay 부동산에서 보기/ })).toHaveLength(2));
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("다른 단지는 따로 묻는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(answer("not_found"));
    render(<>
      <ComplexLink complexId={4} name="헬리오시티아파트" umdName="가락동" />
      <ComplexLink complexId={17} name="가락미륭아파트" umdName="가락동" />
    </>);
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });
});
