import Link from "next/link";
import { AudioLines, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="text-center space-y-5 max-w-md">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-teal-600 via-emerald-500 to-teal-400 text-white shadow-sm shadow-teal-500/20">
          <AudioLines className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">404</h1>
          <p className="mt-1 text-sm font-bold text-slate-700">Page Not Found</p>
          <p className="mt-2 text-xs text-slate-500">
            The page you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-slate-800 transition-all"
        >
          <ArrowLeft className="h-4 w-4" /> Return Home
        </Link>
      </div>
    </div>
  );
}
