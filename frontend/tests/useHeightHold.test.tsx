/**
 * 높이 붙잡기 훅 (012 T003) — FR-001, FR-006, SC-001, research R12-1.
 *
 * - 다시 받는 동안 바꾸기 **직전** 높이를 최소 높이로 붙잡는다(010 FR-023 그대로) — 표가 떨어졌다 붙는 사이 문서가 무너지면 브라우저가 스크롤을 당긴다
 * - **놓을 때 바닥을 남긴다**: 새 내용이 짧아 지금 스크롤을 받치지 못하면(내용의 끝이 창 아래 끝보다 위) 놓는 순간 문서가 줄어 창이 끌려 올라간다 —
 *   FR-001의 실패 양상 *다른 곳에서 일어남*. 그때는 창 아래 끝까지의 높이를 남긴다. 받칠 수 있으면 지금처럼 비운다
 * - 내용의 높이를 잴 수 없으면(0) 지금처럼 놓는다
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useHeightHold } from "@/hooks/useHeightHold";

interface Layout { boxTop: number; boxHeight: number; contentBottom: number }
let layout: Layout;

function Harness({ reload }: { reload: () => Promise<void> }) {
  const { ref, style, hold } = useHeightHold<HTMLDivElement>();
  return (
    <div ref={ref} data-testid="box" style={style}>
      <button type="button" onClick={() => hold(reload)}>바꾸기</button>
      <div data-testid="content">내용</div>
    </div>
  );
}

const rect = (top: number, height: number): DOMRect =>
  ({ top, height, bottom: top + height, left: 0, right: 1000, width: 1000, x: 0, y: top, toJSON: () => ({}) }) as DOMRect;

function gate(): { promise: Promise<void>; release: () => void; fail: () => void } {
  let release: () => void = () => undefined;
  let fail: () => void = () => undefined;
  const promise = new Promise<void>((resolve, reject) => { release = resolve; fail = () => reject(new Error("실패")); });
  return { promise, release, fail };
}

const box = () => screen.getByTestId("box");

beforeEach(() => {
  layout = { boxTop: 0, boxHeight: 1500, contentBottom: 1500 };
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const id = this.getAttribute("data-testid");
    if (id === "box") return rect(layout.boxTop, layout.boxHeight);
    if (id === "content") return rect(layout.contentBottom - 10, 10);
    return rect(0, 0);
  });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("붙잡기", () => {
  it("다시 받는 동안 바꾸기 직전 높이를 최소 높이로 붙잡는다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    expect(box().style.minHeight).toBe("1500px");
    await act(async () => { g.release(); });
  });
});

describe("놓기", () => {
  it("새 내용이 지금 스크롤을 받칠 만큼 높으면 비운다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    layout = { boxTop: -400, boxHeight: 1500, contentBottom: 900 };  // 내용의 끝(900)이 창 아래 끝(800)보다 아래
    await act(async () => { g.release(); });
    expect(box().style.minHeight).toBe("");
  });

  it("새 내용이 짧아 창 아래 끝보다 위에서 끝나면 창 아래 끝까지의 바닥을 남긴다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    // 창이 상자 위 끝에서 400px 아래에 있다. 새 내용은 300px뿐이라 창 아래 끝(800)까지 받치려면 상자가 1200px이어야 한다
    layout = { boxTop: -400, boxHeight: 1500, contentBottom: -100 };
    await act(async () => { g.release(); });
    expect(box().style.minHeight).toBe("1200px");
  });

  it("바닥은 붙잡았던 높이를 넘지 않는다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    layout = { boxTop: 0, boxHeight: 500, contentBottom: 500 };
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    layout = { boxTop: 0, boxHeight: 500, contentBottom: 100 };
    await act(async () => { g.release(); });
    expect(box().style.minHeight).toBe("500px");
  });

  it("내용의 높이를 잴 수 없으면(0) 지금처럼 놓는다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    layout = { boxTop: 0, boxHeight: 1500, contentBottom: 0 };
    await act(async () => { g.release(); });
    expect(box().style.minHeight).toBe("");
  });

  it("다시 받기가 실패해도 놓는다", async () => {
    const g = gate();
    render(<Harness reload={() => g.promise} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    await act(async () => { g.fail(); });
    expect(box().style.minHeight).toBe("");
  });
});

describe("차례", () => {
  it("늦게 끝난 이전 붙잡기가 새 붙잡기를 놓지 않는다", async () => {
    const first = gate();
    const second = gate();
    const reloads = [() => first.promise, () => second.promise];
    let calls = 0;
    render(<Harness reload={() => reloads[calls++]()} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    layout = { ...layout, boxHeight: 1700 };
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    expect(box().style.minHeight).toBe("1700px");
    await act(async () => { first.release(); });
    expect(box().style.minHeight).toBe("1700px");  // 앞 전환이 끝나도 뒤 전환은 아직 받는 중이다
    await act(async () => { second.release(); });
    expect(box().style.minHeight).toBe("");
  });

  it("다음 붙잡기는 남은 바닥 대신 그때의 높이를 붙잡는다", async () => {
    const first = gate();
    const second = gate();
    const reloads = [() => first.promise, () => second.promise];
    let calls = 0;
    render(<Harness reload={() => reloads[calls++]()} />);
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    layout = { boxTop: -400, boxHeight: 1500, contentBottom: -100 };
    await act(async () => { first.release(); });
    expect(box().style.minHeight).toBe("1200px");
    layout = { boxTop: -400, boxHeight: 1200, contentBottom: -100 };
    fireEvent.click(screen.getByRole("button", { name: "바꾸기" }));
    expect(box().style.minHeight).toBe("1200px");
    layout = { boxTop: -400, boxHeight: 1200, contentBottom: 1000 };
    await act(async () => { second.release(); });
    expect(box().style.minHeight).toBe("");
  });
});
