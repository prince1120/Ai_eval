"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Modal } from "@/components/Modal";
import { formatToUserLocalTime } from "@/lib/date-utils";
import {
  FileText,
  PlayCircle,
  ArrowLeft,
  Clock,
  ArrowUpRight,
  Trash2,
  AlertTriangle,
  AlertCircle,
  UserCheck,
  User,
  ChevronDown,
  ChevronUp,
  Sliders,
  MessageSquare,
  AlignLeft,
} from "lucide-react";

export default function TranscriptDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const transcriptId = params.id as string;
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isTranscriptExpanded, setIsTranscriptExpanded] = useState(false);
  const [transcriptViewMode, setTranscriptViewMode] = useState<"dialogue" | "raw">("dialogue");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [analyzeError, setAnalyzeError] = useState("");

  const { data: transcript, isLoading } = useQuery<any>({
    queryKey: ["transcript", transcriptId],
    queryFn: () => apiFetch(`/transcripts/${transcriptId}`),
  });

  const { data: runs = [] } = useQuery<any[]>({
    queryKey: ["transcript-runs", transcriptId],
    queryFn: () => apiFetch(`/transcripts/${transcriptId}/analysis-runs`),
  });

  const { data: templates = [] } = useQuery<any[]>({
    queryKey: ["templates"],
    queryFn: () => apiFetch("/templates"),
  });

  const analyzeMutation = useMutation({
    mutationFn: (templateId?: string) => {
      const payload: any = {};
      if (templateId && templateId.trim() !== "") {
        payload.template_id = templateId;
      }
      return apiFetch(`/transcripts/${transcriptId}/analyze`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (run: any) => {
      setAnalyzeError("");
      queryClient.invalidateQueries({ queryKey: ["transcript-runs", transcriptId] });
      queryClient.invalidateQueries({ queryKey: ["analysis-runs"] });
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      if (run && run.id) {
        router.push(`/analysis-runs/${run.id}`);
      }
    },
    onError: (err: any) => {
      setAnalyzeError(err.message || "Failed to run AI evaluation");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/transcripts/${transcriptId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      router.push("/transcripts");
    },
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12">
        <div className="h-64 rounded-2xl bg-white animate-pulse border border-slate-200" />
      </div>
    );
  }

  if (!transcript) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12 text-center text-slate-500 font-medium">
        Transcript not found.
      </div>
    );
  }

  const dialogueText = transcript.speaker_segments?.diarized_text || transcript.raw_text;
  const activeTemplate = templates.find((t) => t.is_active);

  const renderSpeakerDialogue = (text: string) => {
    const rawLines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const parsedTurns: { speaker: "Agent" | "Customer"; text: string }[] = [];
    let currentSpeaker: "Agent" | "Customer" | null = null;
    let currentText = "";

    for (let line of rawLines) {
      line = line.replace(/^\*\*(Agent|Customer Care|Customer|User):\*\*/i, "$1:");

      const isAgent = /^(Agent|Customer Care):\s*/i.test(line);
      const isCustomer = /^(Customer|User):\s*/i.test(line);

      if (isAgent || isCustomer) {
        if (currentSpeaker && currentText.trim()) {
          parsedTurns.push({ speaker: currentSpeaker, text: currentText.trim() });
        }
        currentSpeaker = isAgent ? "Agent" : "Customer";
        currentText = line.replace(/^(Agent|Customer Care|Customer|User):\s*/i, "");
      } else if (currentSpeaker) {
        currentText += " " + line;
      } else {
        currentSpeaker = "Customer";
        currentText = line;
      }
    }

    if (currentSpeaker && currentText.trim()) {
      parsedTurns.push({ speaker: currentSpeaker, text: currentText.trim() });
    }

    if (parsedTurns.length === 0) {
      return (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 font-mono text-xs leading-relaxed text-slate-800 whitespace-pre-wrap">
          {text}
        </div>
      );
    }

    const displayTurns = isTranscriptExpanded ? parsedTurns : parsedTurns.slice(0, 5);

    return (
      <div className="space-y-4">
        {/* Speaker Turn Attribution Disclaimer Banner */}
        <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5 flex items-start gap-2.5 text-xs text-slate-600 leading-relaxed shadow-2xs">
          <AlertCircle className="h-4 w-4 text-teal-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-slate-900">AI Speaker Separation Notice:</span>{" "}
            Speaker turns (Agent vs. Customer) are automatically formatted based on speech context. Some sentences may occasionally be misattributed due to raw speech transcription. To inspect the 100% exact untouched text, switch to <strong className="text-teal-700 font-bold cursor-pointer hover:underline" onClick={() => setTranscriptViewMode("raw")}>Raw Original Text</strong> mode.
          </div>
        </div>

        <div className="space-y-3">
          {displayTurns.map((turn, idx) => {
            const isAgent = turn.speaker === "Agent";
            const speakerName = isAgent ? "Agent / Support Rep" : "Customer / Caller";

            return (
              <div
                key={idx}
                className={`rounded-2xl p-4 border text-xs leading-relaxed shadow-xs transition-all ${
                  isAgent
                    ? "bg-indigo-50/90 border-indigo-200/90 text-indigo-950 sm:mr-10"
                    : "bg-teal-50/90 border-teal-200/90 text-teal-950 sm:ml-10"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1.5">
                  {isAgent ? (
                    <UserCheck className="h-3.5 w-3.5 text-indigo-700" />
                  ) : (
                    <User className="h-3.5 w-3.5 text-teal-700" />
                  )}
                  <span
                    className={`font-bold text-[11px] uppercase tracking-wider ${
                      isAgent ? "text-indigo-700" : "text-teal-700"
                    }`}
                  >
                    {speakerName}
                  </span>
                </div>
                <p className="mt-1 font-sans text-slate-900 leading-relaxed font-medium">{turn.text}</p>
              </div>
            );
          })}
        </div>

        {parsedTurns.length > 5 && (
          <button
            onClick={() => setIsTranscriptExpanded(!isTranscriptExpanded)}
            className="mt-3 flex items-center justify-center gap-1.5 w-full rounded-xl bg-slate-100 border border-slate-200 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-200 transition-all shadow-2xs"
          >
            {isTranscriptExpanded ? (
              <>
                <ChevronUp className="h-4 w-4" /> Collapse Dialogue
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4" /> Show Full Dialogue ({parsedTurns.length} turns)
              </>
            )}
          </button>
        )}
      </div>
    );
  };

  const renderCleanRawText = (text: string) => {
    const cleanRaw = text
      .split("\n")
      .map((line) => line.replace(/^(\*\*|\b)(Agent|Customer Care|Customer|User)(\*\*|\b):\s*/i, ""))
      .filter((line) => line.trim())
      .join("\n\n");

    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 font-mono text-xs leading-relaxed text-slate-800 whitespace-pre-wrap max-h-96 overflow-y-auto">
        {cleanRaw}
      </div>
    );
  };

  return (
    <div className="page-transition mx-auto max-w-5xl px-4 sm:px-6 py-8 space-y-8">
      {/* Delete Confirmation Modal using Portal */}
      <Modal isOpen={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)}>
        <div className="mx-auto max-w-md rounded-2xl border border-rose-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-rose-600">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <h3 className="text-lg font-bold text-slate-900">Delete Transcript?</h3>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            Are you sure you want to delete this transcript and all associated evaluation runs? This action cannot be undone.
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => setShowDeleteConfirm(false)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 shadow-xs disabled:opacity-50"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete Transcript"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Top Breadcrumb Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/transcripts"
          className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Transcripts
        </Link>

        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 transition-all shadow-xs"
        >
          <Trash2 className="h-3.5 w-3.5" /> Delete Transcript
        </button>
      </div>

      {analyzeError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs font-semibold text-rose-700">
          {analyzeError}
        </div>
      )}

      {/* Main Control Panel */}
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <span className="font-mono text-xs font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200">
            {transcript.source_call_id || `Transcript ID: ${transcript.id.substring(0, 8)}`}
          </span>
          <h1 className="mt-2.5 text-2xl font-extrabold text-slate-900">Call Evaluation Panel</h1>
          <p className="mt-1 text-xs text-slate-500">
            Uploaded on {formatToUserLocalTime(transcript.created_at)}
          </p>
        </div>

        {/* Template Selector & Trigger Button */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="relative">
            <Sliders className="absolute left-3 top-3 h-4 w-4 text-slate-400 pointer-events-none" />
            <select
              value={selectedTemplateId || (activeTemplate?.id || "")}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
              className="w-full sm:w-64 rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-8 py-2.5 text-xs font-bold text-slate-800 appearance-none focus:border-teal-500 focus:outline-none cursor-pointer shadow-xs"
            >
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name} (v{tpl.version}) {tpl.is_active ? "★ Default" : ""}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-3.5 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
          </div>

          <button
            onClick={() => analyzeMutation.mutate(selectedTemplateId || activeTemplate?.id)}
            disabled={analyzeMutation.isPending}
            className="flex items-center justify-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50 transition-all shrink-0"
          >
            <PlayCircle className="h-4 w-4" />
            {analyzeMutation.isPending ? "Evaluating..." : "Run AI Evaluation"}
          </button>
        </div>
      </div>

      {/* Historical Analysis Runs Cards */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Clock className="h-4 w-4 text-indigo-600" /> Historical Evaluation Reports ({runs.length})
          </h2>
          <span className="text-[11px] font-semibold text-slate-500">
            Click &quot;View Scorecard&quot; to inspect parameter breakdowns
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50">
            <p className="text-xs text-slate-500">No evaluation runs executed for this transcript yet.</p>
            <p className="text-[11px] text-slate-400 mt-1">Select a scorecard template above and click &quot;Run AI Evaluation&quot;.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {runs.map((r) => {
              const matchedTemplate = templates.find((t) => t.id === r.template_id);
              const templateDisplayName = matchedTemplate
                ? `${matchedTemplate.name} (v${r.template_version})`
                : (r.template_name ? `${r.template_name} (v${r.template_version})` : `Evaluation Scorecard (v${r.template_version})`);

              return (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/80 p-4 hover:border-teal-400 hover:bg-white transition-all shadow-2xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-xs text-slate-900">
                        {templateDisplayName}
                      </span>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold capitalize border ${
                          r.status === "done"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : r.status === "failed"
                            ? "bg-rose-50 text-rose-700 border-rose-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }`}
                      >
                        {r.status}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 font-mono">
                      Evaluated on {formatToUserLocalTime(r.created_at)}
                    </p>
                  </div>

                  <div className="flex items-center gap-5">
                    {r.overall_score !== null && (
                      <span className="text-base font-black text-teal-600">
                        {r.overall_score.toFixed(1)}%
                      </span>
                    )}
                    <Link
                      href={`/analysis-runs/${r.id}`}
                      className="flex items-center gap-1.5 rounded-lg bg-teal-50 border border-teal-200 px-3 py-1.5 text-xs font-bold text-teal-700 hover:bg-teal-600 hover:text-white transition-all"
                    >
                      View Scorecard <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Transcript Section with View Mode Switcher */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <FileText className="h-4 w-4 text-teal-600" /> Call Transcript Content
          </h2>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs">
            <button
              onClick={() => setTranscriptViewMode("dialogue")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                transcriptViewMode === "dialogue"
                  ? "bg-teal-600 text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <MessageSquare className="h-3.5 w-3.5" /> Dialogue Chat
            </button>
            <button
              onClick={() => setTranscriptViewMode("raw")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                transcriptViewMode === "raw"
                  ? "bg-teal-600 text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <AlignLeft className="h-3.5 w-3.5" /> Raw Original Text
            </button>
          </div>
        </div>

        {transcriptViewMode === "dialogue" ? (
          renderSpeakerDialogue(dialogueText)
        ) : (
          renderCleanRawText(transcript.raw_text)
        )}
      </div>
    </div>
  );
}
