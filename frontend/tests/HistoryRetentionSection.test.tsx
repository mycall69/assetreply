/**
 * 설정 — 이력 보관 기간 (012 T049) — FR-012, contracts/ui-wireframes.md F7.
 *
 * - 서버 값을 보이고 선택지는 여섯(7일·30일·90일·180일·365일·무기한)이다. 기본은 30일이다
 * - 기간을 줄이면 그보다 오래된 항목이 곧바로 지워지고 다시 늘려도 돌아오지 않는다는 사실을 칸 곁에 밝힌다(spec Edge Cases)
 * - 저장은 `PUT {"retentionDays": …}`이고 무기한은 `null`이다. 성공·실패를 다른 절과 같은 자리에서 알린다
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { HistoryRetentionSection } from "@/components/settings/HistoryRetentionSection";
import { historyStub } from "./support/historyStub";

const select = () => screen.getByRole("combobox", { name: "보관 기간" });

describe("이력 보관 기간", () => {
  it("서버 값과 여섯 선택지와 안내를 보인다", async () => {
    render(<HistoryRetentionSection />);
    await waitFor(() => expect(select()).toHaveValue("30"));
    expect([...(select() as HTMLSelectElement).options].map((o) => o.textContent)).toEqual([
      "7일", "30일", "90일", "180일", "365일", "무기한"]);
    expect(screen.getByText(/기간을 줄이면 그보다 오래된 항목이 곧바로 지워지고, 다시 늘려도 돌아오지 않습니다/)).toBeInTheDocument();
    expect(screen.getByText("기본값: 30일")).toBeInTheDocument();
  });

  it("고른 값을 저장하고 알린다 — 무기한은 null이다", async () => {
    render(<HistoryRetentionSection />);
    await waitFor(() => expect(select()).toHaveValue("30"));
    await userEvent.selectOptions(select(), "무기한");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    await screen.findByText("저장했습니다. 기간이 지난 항목은 곧바로 지웠습니다.");
    const put = historyStub.calls().find((c) => c.method === "PUT");
    expect(put).toEqual({ method: "PUT", path: "/api/history/settings", body: { retentionDays: null } });
    expect(select()).toHaveValue("unlimited");
  });

  it("저장에 실패하면 붉은 알림이다", async () => {
    render(<HistoryRetentionSection />);
    await waitFor(() => expect(select()).toHaveValue("30"));
    historyStub.fail("PUT");
    await userEvent.selectOptions(select(), "7일");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("대역이 실패를 만들었다");
  });

  it("불러오지 못하면 알린다", async () => {
    historyStub.fail("GET");
    render(<HistoryRetentionSection />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
