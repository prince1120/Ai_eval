"use client";

import React from "react";

export function TemplateEditSkeleton() {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6 animate-pulse">
      {/* Back button & header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div className="h-4 w-36 rounded-md bg-slate-200" />
        <div className="h-6 w-48 rounded-full bg-slate-100" />
      </div>

      {/* Main Form Box Skeleton */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 space-y-6 shadow-xs">
        {/* Template Name & Description */}
        <div className="space-y-4 border-b border-slate-100 pb-6">
          <div className="space-y-2">
            <div className="h-4 w-32 rounded-md bg-slate-200" />
            <div className="h-10 w-full rounded-xl bg-slate-100" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-40 rounded-md bg-slate-200" />
            <div className="h-16 w-full rounded-xl bg-slate-100" />
          </div>
        </div>

        {/* Parameters Section Header */}
        <div className="flex items-center justify-between pt-2">
          <div className="space-y-1">
            <div className="h-5 w-48 rounded-lg bg-slate-200" />
            <div className="h-3.5 w-64 rounded-md bg-slate-100" />
          </div>
          <div className="flex gap-2">
            <div className="h-9 w-44 rounded-xl bg-teal-50" />
            <div className="h-9 w-36 rounded-xl bg-slate-900/10" />
          </div>
        </div>

        {/* Parameter Cards List Skeleton */}
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-2xl border border-slate-200 bg-slate-50/50 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-5 w-48 rounded-md bg-slate-200" />
                <div className="h-6 w-16 rounded-lg bg-slate-200" />
              </div>
              <div className="h-12 w-full rounded-xl bg-slate-100" />
              <div className="flex justify-between pt-2">
                <div className="h-4 w-32 rounded-md bg-slate-200" />
                <div className="h-4 w-24 rounded-md bg-slate-200" />
              </div>
            </div>
          ))}
        </div>

        {/* Bottom Save Action Bar */}
        <div className="pt-6 border-t border-slate-100 flex justify-end gap-3">
          <div className="h-10 w-24 rounded-xl bg-slate-100" />
          <div className="h-10 w-40 rounded-xl bg-teal-600/30" />
        </div>
      </div>
    </div>
  );
}
