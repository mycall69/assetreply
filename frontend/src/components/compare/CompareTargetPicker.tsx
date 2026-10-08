"use client";

/**
 * 자산군별 대상 고르기 (013 T036) — FR-003, FR-004, ui-wireframes F2.
 *
 * 각 메뉴와 **같은 부품**으로 고른다 — 주식 `StockSearch`(+ 등록 `registerStock`), 가상자산 `CoinSearch`, 예금 투자처 체크박스, 부동산
 * `RegionPicker` → `ComplexPicker` → `AreaBucketPicker`(비교 전용 인스턴스 — 메뉴의 고르기·결과를 건드리지 않는다, research R13-9).
 */
import { useEffect, useRef, useState } from "react";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { AreaBucketPicker } from "@/components/realestate/AreaBucketPicker";
import { ComplexPicker } from "@/components/realestate/ComplexPicker";
import { RegionPicker } from "@/components/realestate/RegionPicker";
import { StockSearch } from "@/components/stock/StockSearch";
import { ApiError, apiClient } from "@/lib/apiClient";
import { createSequence } from "@/lib/searchSequence";
import { registerStock } from "@/lib/stockSelection";
import type {
  CompareAsset,
  CompareMethod,
  CompareTarget,
  DepositInstitution,
  DepositInstitutionsResponse,
  RealEstateRegionLevel,
  StockChoice,
} from "@/lib/types";
import { useCompareRealEstatePicker } from "@/stores/compareRealEstatePicker";
import { InstitutionChecklist } from "./InstitutionChecklist";

interface Props {
  asset: CompareAsset;
  method: CompareMethod;
  targets: CompareTarget[];
  onAdd: (target: CompareTarget) => boolean;
  onRemove: (key: string) => void;
}

function StockPicker({ onAdd }: Pick<Props, "onAdd">) {
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(createSequence());
  async function choose(choice: StockChoice): Promise<void> {
    const id = sequence.current.next();
    setRegistering(true);
    setError(null);
    try {
      const { market, symbol, name, currency } = await registerStock(choice);
      if (!sequence.current.isLatest(id)) return;
      onAdd({ market, symbol, name, currency });
    } catch (err) {
      if (!sequence.current.isLatest(id)) return;
      setError(err instanceof ApiError ? err.message : "고른 종목을 등록하지 못했습니다. 다시 고르세요.");
    } finally {
      if (sequence.current.isLatest(id)) setRegistering(false);
    }
  }
  return (
    <div className="space-y-1">
      <StockSearch value={null} onSelect={(choice) => void choose(choice)} />
      {registering && <p role="status" className="text-xs text-gray-500">종목을 등록하는 중…</p>}
      {error !== null && <p role="alert" className="text-xs text-red-700">{error}</p>}
    </div>
  );
}

function DepositPicker({ method, targets, onAdd, onRemove }: Omit<Props, "asset">) {
  const [institutions, setInstitutions] = useState<DepositInstitution[] | null>(null);
  useEffect(() => {
    let live = true;
    apiClient.get<DepositInstitutionsResponse>("/api/deposit/institutions")
      .then((body) => {
        if (live) setInstitutions(body.institutions);
      })
      // 설명과 적금 여부만 빠진다 — 이름은 고정이라 고를 수 있다(메뉴와 같다).
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  const selected = targets.flatMap((t) => ("institution" in t ? [t.institution] : []));
  return (
    <InstitutionChecklist institutions={institutions} selected={selected}
      product={method === "installment" ? "installment" : "deposit"}
      onToggle={(key, checked) => (checked ? onAdd({ institution: key }) : onRemove(key))} />
  );
}

function RealEstatePicker({ onAdd }: Pick<Props, "onAdd">) {
  const {
    regions, selection, regionCollecting, regionProgress, regionFailure, complexes, tradeProgress, detailsProgress,
    areas, areasCollecting, error, loadSidos, selectSido, selectSgg, selectUmd, selectComplex, selectArea, dispose,
  } = useCompareRealEstatePicker();
  useEffect(() => {
    void loadSidos();
    return dispose;
  }, [loadSidos, dispose]);

  function selectRegion(level: RealEstateRegionLevel, code: string): void {
    if (level === "sido") void selectSido(code);
    else if (level === "sgg") void selectSgg(code);
    else void selectUmd(code);
  }

  const sggName = regions.sgg?.find((r) => r.code === selection.sgg)?.name ?? null;
  const waitingForTrades = areas === null
    && (areasCollecting !== null || (complexes !== null && complexes.trades.state !== "collected"));
  const complex = complexes?.items.find((c) => c.complexId === selection.complexId) ?? null;
  const bucket = areas?.buckets.find((b) => b.key === selection.area) ?? null;
  const ready = complex !== null && bucket !== null && complexes !== null;

  return (
    <div className="space-y-3">
      <RegionPicker regions={regions} selection={selection} onSelect={selectRegion}
        collecting={regionCollecting} progress={regionProgress} failure={regionFailure} />
      <ComplexPicker complexes={complexes} value={selection.complexId}
        onChange={(complexId) => void selectComplex(complexId)} sggName={sggName}
        tradeProgress={tradeProgress} detailsProgress={detailsProgress} />
      <AreaBucketPicker areas={areas} value={selection.area} onChange={selectArea} waitingForTrades={waitingForTrades} />
      <button type="button" disabled={!ready}
        className="rounded border border-gray-300 px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        onClick={() => {
          if (!ready) return;
          onAdd({ complexId: complex.complexId, name: complex.name, umdName: complexes.umd.name, area: bucket.key,
            areaLabel: bucket.label });
        }}>
        더하기
      </button>
      {error !== null && <p role="alert" className="text-xs text-red-700">{error}</p>}
    </div>
  );
}

export function CompareTargetPicker({ asset, method, targets, onAdd, onRemove }: Props) {
  switch (asset) {
    case "stock":
      return <StockPicker onAdd={onAdd} />;
    case "crypto":
      return (
        <CoinSearch value={null} onSelect={(coin) => onAdd({
          coinId: coin.coinId, symbol: coin.symbol, name: coin.name, nameKo: coin.nameKo, currency: coin.currency })} />
      );
    case "deposit":
      return <DepositPicker method={method} targets={targets} onAdd={onAdd} onRemove={onRemove} />;
    case "realestate":
      return <RealEstatePicker onAdd={onAdd} />;
  }
}
