"use client";

import React from "react";

export function DashboardSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-8 space-y-6 sm:space-y-8 animate-pulse">
      {/* Header skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div className="space-y-2">
          <div className="h-4 w-32 rounded-full bg-slate-200" />
          <div className="h-8 w-64 rounded-xl bg-slate-200" />
          <div className="h-4 w-96 rounded-lg bg-slate-100" />
        </div>
        <div className="h-10 w-36 rounded-xl bg-slate-200" />
      </div>

      {/* Overview Cards Row Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-3.5 w-28 rounded-md bg-slate-200" />
              <div className="h-4 w-4 rounded-md bg-slate-200" />
            </div>
            <div className="h-8 w-24 rounded-lg bg-slate-300" />
            <div className="h-3.5 w-36 rounded-md bg-slate-100 pt-2 border-t border-slate-100" />
          </div>
        ))}
      </div>

      {/* Distribution Chart Widget Skeleton */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="h-5 w-48 rounded-lg bg-slate-200" />
          <div className="h-4 w-32 rounded-md bg-slate-100" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-slate-200 p-4 space-y-3 bg-slate-50">
              <div className="flex justify-between">
                <div className="h-4 w-28 rounded-md bg-slate-200" />
                <div className="h-4 w-8 rounded-md bg-slate-200" />
              </div>
              <div className="h-2 w-full rounded-full bg-slate-200" />
            </div>
          ))}
        </div>
      </div>

      {/* Explorer Table Skeleton */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="h-6 w-56 rounded-lg bg-slate-200" />
          <div className="h-9 w-64 rounded-xl bg-slate-200" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 w-full rounded-xl bg-slate-50 border border-slate-100" />
          ))}
        </div>
      </div>
    </div>
  );
}
