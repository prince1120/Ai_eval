"use client";

import { useEffect } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-center space-y-4">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 border border-rose-200 text-rose-600">
        <AlertCircle className="h-7 w-7" />
      </div>
      <h2 className="text-xl font-extrabold text-slate-900">Something went wrong</h2>
      <p className="text-xs text-slate-500 max-w-md mx-auto">
        An unexpected error occurred while loading this page. You can try again, or return to the dashboard.
      </p>
      <button
        onClick={() => reset()}
        className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-teal-700 transition-all"
      >
        <RotateCcw className="h-3.5 w-3.5" /> Try Again
      </button>
    </div>
  );
}
