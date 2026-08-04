"use client";

import React from "react";

export function TemplatesSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8 animate-pulse">
      {/* Header Banner Skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div className="space-y-2">
          <div className="h-8 w-64 rounded-xl bg-slate-200" />
          <div className="h-4 w-96 rounded-lg bg-slate-100" />
        </div>
        <div className="flex gap-3">
          <div className="h-10 w-48 rounded-xl bg-slate-200" />
          <div className="h-10 w-44 rounded-xl bg-slate-200" />
        </div>
      </div>

      {/* Grid Cards Skeleton */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-5 w-12 rounded-full bg-slate-200" />
              <div className="h-5 w-28 rounded-full bg-slate-200" />
            </div>

            <div className="h-6 w-48 rounded-lg bg-slate-300" />
            <div className="h-10 w-full rounded-lg bg-slate-100" />

            <div className="flex gap-4 pt-4 border-t border-slate-100">
              <div className="h-4 w-24 rounded-md bg-slate-200" />
              <div className="h-4 w-20 rounded-md bg-slate-200" />
            </div>

            <div className="flex justify-between pt-4 border-t border-slate-100">
              <div className="h-8 w-20 rounded-xl bg-slate-200" />
              <div className="h-8 w-24 rounded-xl bg-slate-200" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
