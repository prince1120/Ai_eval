"use client";

import React from "react";

export function TeamSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8 animate-pulse">
      {/* Header Banner Skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div className="space-y-2">
          <div className="h-8 w-64 rounded-xl bg-slate-200" />
          <div className="h-4 w-96 rounded-lg bg-slate-100" />
        </div>
        <div className="h-10 w-44 rounded-xl bg-slate-200" />
      </div>

      {/* Toolbar Skeleton */}
      <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="h-9 w-64 rounded-xl bg-slate-200" />
        <div className="h-6 w-32 rounded-full bg-slate-100" />
      </div>

      {/* Team Cards Grid Skeleton */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-10 w-10 rounded-full bg-slate-200" />
              <div className="h-5 w-20 rounded-full bg-slate-200" />
            </div>
            <div className="space-y-1">
              <div className="h-5 w-40 rounded-md bg-slate-300" />
              <div className="h-3.5 w-48 rounded-md bg-slate-100" />
            </div>
            <div className="pt-4 border-t border-slate-100 flex justify-between">
              <div className="h-7 w-20 rounded-lg bg-slate-200" />
              <div className="h-7 w-20 rounded-lg bg-slate-200" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
