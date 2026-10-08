/**
 * 비교 저장 칸 (013 T066) — FR-016, ui-wireframes F9.
 *
 * "저장"을 누르면 이름 칸이 열리고 처음 값은 자동 이름이다. 공백만이면 저장 단추가 꺼진다. 저장은 앞뒤 공백을 뺀 이름이다. 저장할 수 없으면(흐림·막힘·결과
 * 없음) 여는 단추가 꺼지고 까닭이 보인다.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SaveComparisonForm } from "@/components/compare/SaveComparisonForm";

function draw(props: Partial<Parameters<typeof SaveComparisonForm>[0]> = {}) {
  const onSave = vi.fn(async () => true);
  render(<SaveComparisonForm defaultName="주식 3개 · 2020-01-02 · 일시금" reason={null} saving={false} onSave={onSave} {...props} />);
  return onSave;
}

const nameBox = () => screen.getByRole("textbox", { name: "비교 이름" });

describe("저장 칸", () => {
  it("열면 이름 칸에 자동 이름이다", () => {
    draw();
    expect(screen.queryByRole("textbox", { name: "비교 이름" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(nameBox()).toHaveValue("주식 3개 · 2020-01-02 · 일시금");
  });

  it("공백만이면 저장 단추가 꺼진다", () => {
    draw();
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    fireEvent.change(nameBox(), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  it("취소하면 닫히고 저장하지 않는다", () => {
    const onSave = draw();
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    fireEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(screen.queryByRole("textbox", { name: "비교 이름" })).toBeNull();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("저장은 앞뒤 공백을 뺀 이름이고 성공하면 닫힌다", async () => {
    const onSave = draw();
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    fireEvent.change(nameBox(), { target: { value: "  반도체 셋  " } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith("반도체 셋");
    await waitFor(() => expect(screen.queryByRole("textbox", { name: "비교 이름" })).toBeNull());
  });

  it("실패하면 열린 채 이름이 남는다", async () => {
    const failing = vi.fn(async () => false);
    draw({ onSave: failing });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    fireEvent.change(nameBox(), { target: { value: "반도체 셋" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(failing).toHaveBeenCalledWith("반도체 셋"));
    expect(nameBox()).toHaveValue("반도체 셋");
  });

  it("보내는 중에는 저장 단추가 꺼진다", () => {
    draw({ saving: true });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  it("저장할 수 없으면 여는 단추가 꺼지고 까닭이 보인다", () => {
    draw({ reason: "다시 실행한 뒤 저장할 수 있습니다" });
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    expect(screen.getByText("다시 실행한 뒤 저장할 수 있습니다")).toBeInTheDocument();
  });
});
