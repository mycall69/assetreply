"use client";

/** 수집 현황 페이지 (US4) — contracts/ui-sketches.md S4·S6. */

import { useEffect } from "react";
import { CollectionProgress } from "@/components/CollectionProgress";
import { CollectionStatus } from "@/components/CollectionStatus";
import { useCollectionStore } from "@/stores/collectionStore";

export default function CollectionPage() {
  const { coverage, jobs, progress, error, refresh, startCollection, stopWatching } =
    useCollectionStore();

  useEffect(() => {
    void refresh();
    return () => stopWatching();
  }, [refresh, stopWatching]);

  return (
    <div className="space-y-6">
      {error && (
        <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          {error}
        </p>
      )}

      {progress && (
        <CollectionProgress state={progress} onRetry={() => void startCollection()} />
      )}

      <CollectionStatus
        coverage={coverage}
        jobs={jobs}
        onStart={() => void startCollection()}
      />
    </div>
  );
}
