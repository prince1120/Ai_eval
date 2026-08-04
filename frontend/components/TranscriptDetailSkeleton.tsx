"use client";

import React from "react";

export function TranscriptDetailSkeleton() {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6 animate-pulse">
      {/* Top Back Link & Action Row */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div className="h-4 w-36 rounded-md bg-slate-200" />
        <div className="h-4 w-28 rounded-md bg-slate-200" />
      </div>

      {/* Main Header Banner Card */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="h-7 w-64 rounded-xl bg-slate-200" />
            <div className="flex gap-2">
              <div className="h-4 w-32 rounded-md bg-slate-100" />
              <div className="h-4 w-20 rounded-md bg-slate-100" />
            </div>
          </div>
          <div className="h-10 w-44 rounded-xl bg-teal-600/30" />
        </div>

        {/* Audio Player Bar Skeleton */}
        <div className="h-14 w-full rounded-2xl bg-slate-100 border border-slate-200 p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-slate-200" />
            <div className="h-4 w-24 rounded-md bg-slate-200" />
          </div>
          <div className="h-3 w-48 rounded-full bg-slate-200" />
        </div>
      </div>

      {/* Grid Content Layout */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Dialogue Preview Container */}
        <div className="md:col-span-2 rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="h-5 w-40 rounded-lg bg-slate-200" />
            <div className="h-8 w-32 rounded-xl bg-slate-100" />
          </div>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className={`p-4 rounded-2xl border ${i % 2 === 0 ? "bg-teal-50/40 border-teal-100 ml-6" : "bg-slate-50 border-slate-100 mr-6"} space-y-2`}>
                <div className="h-3 w-20 rounded-md bg-slate-300" />
                <div className="h-4 w-full rounded-md bg-slate-200" />
                <div className="h-4 w-3/4 rounded-md bg-slate-200" />
              </div>
            ))}
          </div>
        </div>

        {/* Evaluation Runs Cards Sidebar */}
        <div className="rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
          <div className="h-5 w-36 rounded-lg bg-slate-200 border-b border-slate-100 pb-3" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-2xl bg-slate-50 border border-slate-200 p-3 space-y-2" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
