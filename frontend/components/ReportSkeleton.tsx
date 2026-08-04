"use client";

import React from "react";

export function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8 space-y-6 animate-pulse">
      {/* Top action bar skeleton */}
      <div className="flex items-center justify-between gap-4">
        <div className="h-4 w-32 rounded-lg bg-slate-200" />
        <div className="flex items-center gap-2">
          <div className="h-8 w-28 rounded-xl bg-slate-200" />
          <div className="h-8 w-28 rounded-xl bg-slate-200" />
          <div className="h-8 w-28 rounded-xl bg-slate-200" />
        </div>
      </div>

      {/* Audio player skeleton */}
      <div className="h-20 w-full rounded-2xl bg-slate-200/80" />

      {/* Report Header Card Skeleton */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 space-y-6 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <div className="space-y-3 flex-1">
            <div className="flex gap-2">
              <div className="h-6 w-40 rounded-full bg-slate-200" />
              <div className="h-6 w-28 rounded-full bg-slate-200" />
            </div>
            <div className="h-8 w-72 rounded-xl bg-slate-200" />
            <div className="h-4 w-96 rounded-lg bg-slate-100" />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <div className="h-4 w-48 rounded-lg bg-slate-100" />
              <div className="h-4 w-48 rounded-lg bg-slate-100" />
              <div className="h-4 w-48 rounded-lg bg-slate-100" />
              <div className="h-4 w-48 rounded-lg bg-slate-100" />
            </div>
          </div>

          <div className="flex flex-col items-center gap-3">
            <div className="h-32 w-32 rounded-full bg-slate-200" />
            <div className="h-6 w-24 rounded-full bg-slate-200" />
          </div>
        </div>
      </div>

      {/* Sticky Bar Skeleton */}
      <div className="h-14 w-full rounded-2xl bg-slate-200" />

      {/* Overview Bar Chart Skeleton */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <div className="h-5 w-48 rounded-lg bg-slate-200" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-4 w-44 rounded-md bg-slate-200 shrink-0" />
              <div className="h-4 flex-1 rounded-full bg-slate-100" />
              <div className="h-4 w-12 rounded-md bg-slate-200 shrink-0" />
            </div>
          ))}
        </div>
      </div>

      {/* Parameter Cards Skeleton */}
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-5 w-64 rounded-lg bg-slate-200" />
              <div className="h-6 w-16 rounded-lg bg-slate-200" />
            </div>
            <div className="h-4 w-full rounded-lg bg-slate-100" />
            <div className="h-16 w-full rounded-xl bg-slate-50" />
          </div>
        ))}
      </div>
    </div>
  );
}
