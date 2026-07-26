import { Loader2 } from "lucide-react";

export default function DashboardLoading() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-50">
      <div className="text-center space-y-3">
        <Loader2 className="mx-auto h-9 w-9 text-teal-600 animate-spin" />
        <p className="text-xs font-bold text-slate-500">Loading...</p>
      </div>
    </div>
  );
}
