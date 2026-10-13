/**
 * 차례 한도 (014 반복 2026-10-13 T217) — spec FR-046, research R14-36.
 *
 * 화면은 같은 주소(Next.js 경유)로 HTTP/1.1 요청을 보내고 Chrome은 같은 주소에 연결을 6개까지 연다. 진행 구독(`EventSource`)도 그 6개를 쓴다.
 * 투자 비교 대상이 100개면 요청·구독을 한꺼번에 열 수 없다 — 구독이 연결을 다 차지하면 다른 대상의 요청과 화면의 다른 요청이 수집이 끝날
 * 때까지 오류 없이 멈춘다. 그래서 **들어온 차례로 한도만큼만** 돌리고 나머지는 기다린다.
 *
 * - 비교 요청 3 · 진행 구독 2(합 5 — 하나를 화면의 다른 요청에 남긴다) · 확대 구간 요청 3. 설정이 아니라 상수다
 * - 순수하다 — 타이머·DOM·요청 없이 자리만 센다. 시작은 늘 다음 마이크로태스크 이후다(`enter`가 그만두기 함수를 먼저 돌려준다)
 * - 기다리는 중에 그만두면 줄에서 빠지고, 시작한 것을 그만두면 `start`가 돌려준 멈춤을 부르고 자리를 비운다. 여러 번 불러도 한 번이다
 */

/** 한 번에 보내는 투자 비교 요청 수. */
export const COMPARE_REQUESTS = 3;
/** 한 번에 여는 진행 구독 수. */
export const COMPARE_STREAMS = 2;
/** 한 번에 보내는 확대 구간 요청 수. */
export const DETAIL_REQUESTS = 3;

/** 자리를 받으면 부른다. 자리를 비우는 함수를 받고, 그만둘 때 부를 멈춤을 돌려줄 수 있다. */
export type LimitedStart = (release: () => void) => (() => void) | void;

export interface Limiter {
  /** 자리가 나면 `start`를 부른다. 돌려준 함수는 그만두기다(기다리는 중이면 줄에서 빼고, 시작했으면 멈추고 자리를 비운다). */
  enter: (start: LimitedStart) => () => void;
  /** 자리를 받아 `task`를 돌리고, 끝나면(성공·실패 모두) 자리를 비운다. 값과 실패를 그대로 넘긴다. */
  run: <T>(task: () => Promise<T>) => Promise<T>;
  /** 기다리는 것을 모두 줄에서 뺀다 — 시작한 것은 그대로다. `enter` 전용이다(`run`의 약속은 끝나지 않게 된다). */
  clearWaiting: () => void;
}

interface Entry {
  state: "waiting" | "running" | "done";
  start: LimitedStart;
  stop?: () => void;
}

/** `start` 안에서 자리를 비웠는가 — 상태는 부른 함수 안에서 바뀐다(흐름 좁히기 밖). */
const finished = (entry: Entry): boolean => entry.state === "done";

export function createLimiter(limit: number): Limiter {
  let active = 0;
  let queue: Entry[] = [];

  const finish = (entry: Entry) => {
    if (entry.state !== "running") return;
    entry.state = "done";
    active -= 1;
    pump();
  };

  function pump(): void {
    while (active < limit && queue.length > 0) {
      const entry = queue.shift() as Entry;
      if (entry.state !== "waiting") continue;
      entry.state = "running";
      active += 1;
      const stop = entry.start(() => finish(entry));
      if (typeof stop !== "function") continue;
      // 시작하는 동안 그만뒀으면(같은 차례에 끝 사건이 왔으면) 곧바로 멈춘다 — 열어 둔 채 남기지 않는다.
      if (finished(entry)) stop();
      else entry.stop = stop;
    }
  }

  return {
    enter: (start) => {
      const entry: Entry = { state: "waiting", start };
      queue.push(entry);
      queueMicrotask(pump);
      return () => {
        if (entry.state === "waiting") {
          entry.state = "done";
          queue = queue.filter((e) => e !== entry);
          return;
        }
        if (entry.state !== "running") return;
        const stop = entry.stop;
        entry.stop = undefined;
        stop?.();
        finish(entry);
      };
    },
    run: (task) => new Promise((resolve, reject) => {
      queue.push({
        state: "waiting",
        start: (release) => {
          Promise.resolve().then(task).then(resolve, reject).finally(release);
        },
      });
      queueMicrotask(pump);
    }),
    clearWaiting: () => {
      for (const entry of queue) entry.state = "done";
      queue = [];
    },
  };
}
