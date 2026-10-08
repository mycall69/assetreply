/**
 * 비교 화면의 부동산 고르기 (013 T033) — FR-003, research R13-9.
 *
 * 부동산 메뉴와 **같은 상태 생성기**(`realEstateStateCreator`)로 만든 따로 된 인스턴스다. 고르기 흐름(시·도 → 시·군·구 → 법정동 → 단지 →
 * 평형, 목록 202·진행)이 한 벌이라 메뉴와 비교의 고르기가 갈라지지 않는다. 비교는 이 인스턴스의 고르기만 쓰고 `run`(이력을 저장한다)은
 * 부르지 않는다 — 계산은 비교 경로가 한다.
 */
import { create } from "zustand";
import { realEstateStateCreator, type RealEstateState } from "./realEstateStore";

export const useCompareRealEstatePicker = create<RealEstateState>()(realEstateStateCreator);
