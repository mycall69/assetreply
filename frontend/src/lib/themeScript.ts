/**
 * 깜빡임 방지 스크립트 (014 반복 2026-10-10c T135) — FR-030, SC-015, data-model §9, research R14-23.
 *
 * 루트 배치(`app/layout.tsx`)가 `<head>`에 글자로 넣는다 — 화면을 그리기 **전에** 브라우저 저장소를 읽어 `<html>`에 `dark` 클래스를 단다.
 * React가 붙은 뒤에 읽으면 새로고침마다 밝은 화면이 한 번 그려졌다 바뀐다(FR-030 실패 양상 — 늦게 일어남). 저장값이 `"dark"`가 아니거나
 * 저장소를 읽을 수 없으면(사생활 모드) 아무것도 하지 않는다 — 밝게, 오류 없음.
 */

/** 브라우저 저장소 키. 값은 `"light"`·`"dark"`. */
export const THEME_KEY = "assetreplay.theme";

export const THEME_SCRIPT = `(function(){try{if(localStorage.getItem(${JSON.stringify(THEME_KEY)})==="dark"){document.documentElement.classList.add("dark")}}catch(e){}})();`;
