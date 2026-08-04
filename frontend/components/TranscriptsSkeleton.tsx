"use client";

import React from "react";

export function TranscriptsSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6 animate-pulse">
      {/* Header Banner Skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div className="space-y-2">
          <div className="h-8 w-72 rounded-xl bg-slate-200" />
          <div className="h-4 w-96 rounded-lg bg-slate-100" />
        </div>
        <div className="flex gap-3">
          <div className="h-10 w-36 rounded-xl bg-slate-200" />
          <div className="h-10 w-44 rounded-xl bg-slate-200" />
        </div>
      </div>

      {/* Toolbar Skeleton */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="h-9 w-64 rounded-xl bg-slate-200" />
        <div className="flex gap-3">
          <div className="h-9 w-48 rounded-xl bg-slate-100" />
          <div className="h-9 w-20 rounded-xl bg-slate-200" />
        </div>
      </div>

      {/* Cards Grid Skeleton */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="flex flex-col justify-between rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
            <div className="space-y-3">
              {/* Card Header Row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded-sm bg-slate-200" />
                  <div className="h-5 w-44 rounded-lg bg-slate-200" />
                </div>
                <div className="h-5 w-14 rounded-full bg-rose-100" />
              </div>

              {/* Audio & Language Badges */}
              <div className="flex gap-2">
                <div className="h-6 w-24 rounded-lg bg-teal-50" />
                <div className="h-6 w-16 rounded-lg bg-purple-50" />
              </div>

              {/* Dialogue Box Preview */}
              <div className="h-24 w-full rounded-2xl bg-slate-50 border border-slate-100 p-3 space-y-2">
                <div className="h-3 w-full rounded-md bg-slate-200" />
                <div className="h-3 w-4/5 rounded-md bg-slate-200" />
                <div className="h-3 w-2/3 rounded-md bg-slate-100" />
              </div>
            </div>

            {/* Footer Row */}
            <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
              <div className="h-4 w-24 rounded-md bg-slate-200" />
              <div className="h-9 w-28 rounded-xl bg-slate-200" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
