"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { DynamicResultsList } from "@/components/DynamicResultsList";
import { AudioPlayer } from "@/components/AudioPlayer";
import { exportSingleRunToCSV, exportSingleRunToJSON } from "@/lib/export-utils";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Download,
  FileSpreadsheet,
  FileCode,
  RefreshCw,
  Printer,
  FileText,
} from "lucide-react";

const MAX_POLL_MS = 5 * 60 * 1000;

export default function AnalysisRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const runId = params.id as string;
  const pollStartRef = useRef<number | null>(null);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const [retryError, setRetryError] = useState("");

  const { data: run, isLoading, error } = useQuery<any>({
    queryKey: ["analysis-run", runId],
    queryFn: () => apiFetch(`/analysis-runs/${runId}`),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "pending" || data.status === "processing")) {
        if (pollStartRef.current === null) {
          pollStartRef.current = Date.now();
        }
        if (Date.now() - pollStartRef.current > MAX_POLL_MS) {
          setPollTimedOut(true);
          return false;
        }
        return 2000;
      }
      pollStartRef.current = null;
      return false;
    },
  });

  const { data: transcript } = useQuery<any>({
    queryKey: ["transcript", run?.transcript_id],
    queryFn: () => apiFetch(`/transcripts/${run.transcript_id}`),
    enabled: !!run?.transcript_id,
  });

  // Fetch template info for report metadata
  const { data: templates = [] } = useQuery<any[]>({
    queryKey: ["templates"],
    queryFn: () => apiFetch("/templates"),
    enabled: run?.status === "done",
  });

  const matchedTemplate = templates.find((t) => t.id === run?.template_id);
  const templateName =
    matchedTemplate?.name ||
    run?.template_name ||
    "Call Quality Scorecard";
  const templateVersion = run?.template_version;

  const retryMutation = useMutation({
    mutationFn: () => {
      const payload: Record<string, string> = {};
      if (run?.template_id) {
        payload.template_id = run.template_id;
      }
      return apiFetch<{ id: string }>(`/transcripts/${run.transcript_id}/analyze`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (newRun) => {
      setRetryError("");
      queryClient.invalidateQueries({ queryKey: ["analysis-runs"] });
      queryClient.invalidateQueries({ queryKey: ["transcript-runs", run?.transcript_id] });
      if (newRun?.id) {
        router.push(`/analysis-runs/${newRun.id}`);
      }
    },
    onError: (err: unknown) => {
      setRetryError(err instanceof Error ? err.message : "Failed to re-run analysis");
    },
  });

  const handlePrint = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-12 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 text-teal-600 animate-spin" />
        <p className="text-sm font-semibold text-slate-500">Loading analysis run...</p>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-12 text-center space-y-4">
        <AlertCircle className="mx-auto h-12 w-12 text-rose-500" />
        <p className="text-sm font-semibold text-slate-700">Failed to load analysis run.</p>
        <Link href="/dashboard" className="text-xs text-teal-600 font-bold hover:underline">
          Return to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
      {/* Navigation & Export Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 print:hidden">
        <Link
          href={`/transcripts/${run.transcript_id}`}
          className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Transcript
        </Link>

        {run.status === "done" && (
          <div className="flex items-center gap-2 flex-wrap">
            {/* View Transcript Jump Button */}
            <button
              onClick={() => {
                const el = document.getElementById("transcript-section");
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" });
                }
              }}
              className="flex items-center gap-1.5 rounded-xl border border-teal-200 bg-teal-50 px-3.5 py-1.5 text-xs font-bold text-teal-800 hover:bg-teal-100 transition-all shadow-xs"
              title="Jump to Call Transcript"
            >
              <FileText className="h-3.5 w-3.5 text-teal-600" /> View Transcript
            </button>

            {/* Print / PDF */}
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-bold text-slate-800 hover:border-indigo-400 hover:text-indigo-700 transition-all shadow-xs"
              title="Print or Save as PDF"
            >
              <Printer className="h-3.5 w-3.5 text-indigo-600" /> Print / PDF
            </button>

            <span className="text-xs font-bold text-slate-500 flex items-center gap-1 ml-1">
              <Download className="h-3.5 w-3.5" /> Download:
            </span>
            <button
              onClick={() => exportSingleRunToCSV(run, transcript, { templateName, templateVersion })}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-bold text-slate-800 hover:border-teal-500 hover:text-teal-600 transition-all shadow-xs"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" /> CSV Excel
            </button>
            <button
              onClick={() => exportSingleRunToJSON(run, transcript, { templateName, templateVersion })}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-bold text-slate-800 hover:border-teal-500 hover:text-teal-600 transition-all shadow-xs"
            >
              <FileCode className="h-3.5 w-3.5 text-indigo-600" /> JSON Data
            </button>
          </div>
        )}
      </div>

      {/* Processing State */}
      {(run.status === "pending" || run.status === "processing") && (
        <div className="rounded-2xl border border-teal-200 bg-teal-50/50 p-8 text-center space-y-4">
          <Loader2 className="mx-auto h-10 w-10 text-teal-600 animate-spin" />
          <h2 className="text-xl font-extrabold text-slate-900">AI Analysis in Progress</h2>
          <p className="text-xs text-slate-600 max-w-md mx-auto">
            {pollTimedOut
              ? "Still processing — this is taking longer than expected. Refresh this page to check the latest status."
              : "Evaluating transcript against selected scorecard parameters..."}
          </p>
        </div>
      )}

      {/* Failure State */}
      {run.status === "failed" && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-8 text-center space-y-4">
          <AlertCircle className="mx-auto h-10 w-10 text-rose-600" />
          <h2 className="text-xl font-extrabold text-slate-900">Analysis Job Failed</h2>
          <p className="text-xs text-rose-700 font-mono bg-white p-4 rounded-xl max-w-xl mx-auto border border-rose-200">
            {run.error_message || "An unexpected error occurred during execution."}
          </p>
          <div className="flex flex-col items-center gap-2 pt-2">
            <button
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-teal-700 disabled:opacity-60 disabled:cursor-not-allowed transition-all shadow-xs"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${retryMutation.isPending ? "animate-spin" : ""}`} />
              {retryMutation.isPending ? "Re-running analysis..." : "Retry Analysis"}
            </button>
            {retryError && (
              <p className="text-xs font-semibold text-rose-600">{retryError}</p>
            )}
          </div>
        </div>
      )}

      {/* Audio Player (if transcript has recording) */}
      {run.status === "done" && transcript?.id && (
        <AudioPlayer
          transcriptId={transcript.id}
          detectedLanguage={transcript.detected_language}
          durationSeconds={transcript.audio_duration_seconds}
        />
      )}

      {/* Completed Results — Full Professional Report */}
      {run.status === "done" && (
        <DynamicResultsList
          overallScore={run.overall_score}
          parameterResults={run.parameter_results || []}
          sectionResults={run.section_results || []}
          llmModelUsed={run.llm_model_used}
          templateName={templateName}
          templateVersion={templateVersion}
          callReference={transcript?.source_call_id || undefined}
          evaluatedAt={run.completed_at || run.created_at}
          creator={run.creator}
          tokenUsage={run.token_usage}
          transcript={transcript}
        />
      )}
    </div>
  );
}
