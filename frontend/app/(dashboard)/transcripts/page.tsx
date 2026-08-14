"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { exportBulkRunsToCSV } from "@/lib/export-utils";
import { Modal } from "@/components/Modal";
import { TranscriptsSkeleton } from "@/components/TranscriptsSkeleton";
import { useToast } from "@/components/Toast";
import {
  FileText,
  Plus,
  UploadCloud,
  ArrowRight,
  Mic,
  FileCode,
  Trash2,
  AlertTriangle,
  Download,
  CheckSquare,
  Square,
  Search,
  Loader2,
  CheckCircle2,
  Cpu,
  UserCheck,
  LayoutGrid,
  List,
  Headphones,
  Globe,
  Clock,
  Sparkles,
  TrendingUp,
  AlertCircle,
  XCircle,
  PhoneCall,
  Calendar,
  ChevronDown,
} from "lucide-react";


// A queued transcription can sit behind a provider rate limit for a while, so
// poll generously rather than failing the upload the moment it is slow.
const TRANSCRIPTION_POLL_MS = 2000;
const TRANSCRIPTION_TIMEOUT_MS = 15 * 60 * 1000;

async function waitForTranscription(
  transcriptId: string,
  onStatus?: (status: string) => void
): Promise<any> {
  const deadline = Date.now() + TRANSCRIPTION_TIMEOUT_MS;

  while (Date.now() < deadline) {
    const t: any = await apiFetch(`/transcripts/${transcriptId}`);
    onStatus?.(t.status);

    if (t.status === "transcription_failed") {
      throw new Error(
        "Transcription failed for this recording. Open the call and use Retry Transcription."
      );
    }
    // "completed" covers transcripts created before the queue existed.
    if (t.status === "transcribed" || t.status === "completed") {
      return t;
    }
    await new Promise((r) => setTimeout(r, TRANSCRIPTION_POLL_MS));
  }

  throw new Error(
    "Still transcribing - it is taking longer than usual. The call will appear in the list when it finishes."
  );
}

export default function TranscriptsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showToast } = useToast();
  const canUpload = user?.role === "admin" || user?.role === "evaluator";
  const canDelete = user?.role === "admin";

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"text" | "audio">("audio");
  const [rawText, setRawText] = useState("");
  const [sourceCallId, setSourceCallId] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [selectedUploadTemplateId, setSelectedUploadTemplateId] = useState<string>("");
  const [transcriptToDelete, setTranscriptToDelete] = useState<any | null>(null);
  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [bulkDeleteResult, setBulkDeleteResult] = useState("");

  // View Mode state (Grid vs Table)
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  // Real-time processing progress states
  const [currentProcessingStep, setCurrentProcessingStep] = useState<number>(0);
  const [currentFileProcessingName, setCurrentFileProcessingName] = useState<string>("");

  // Selection & Date Filtering State
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFilter, setDateFilter] = useState<"all" | "today" | "yesterday" | "7days" | "30days" | "custom">("all");
  const [customStartDate, setCustomStartDate] = useState<string>("");
  const [customEndDate, setCustomEndDate] = useState<string>("");

  const { data: transcripts = [], isLoading } = useQuery<any[]>({
    queryKey: ["transcripts"],
    queryFn: () => apiFetch("/transcripts"),
  });

  const { data: runs = [] } = useQuery<any[]>({
    queryKey: ["analysis-runs"],
    queryFn: () => apiFetch("/analysis-runs"),
  });

  const { data: templates = [] } = useQuery<any[]>({
    queryKey: ["templates"],
    queryFn: () => apiFetch("/templates"),
  });

  const activeTemplate = templates.find((t) => t.is_active) || templates[0];

  const uploadTextMutation = useMutation({
    mutationFn: (data: any) =>
      apiFetch("/transcripts", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: (newTranscript: any) => {
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      closeModal();
      if (newTranscript && newTranscript.id) {
        router.push(`/transcripts/${newTranscript.id}`);
      }
    },
  });

  const uploadAudioMutation = useMutation({
    mutationFn: async () => {
      if (selectedFiles.length === 0) return;

      const filesToProcess = selectedFiles.slice(0, 5);
      let lastCreatedTranscript: any = null;

      // Determine which template ID to use
      const templateIdToUse = selectedUploadTemplateId || activeTemplate?.id || "";

      for (let i = 0; i < filesToProcess.length; i++) {
        const file = filesToProcess[i];
        setCurrentFileProcessingName(file.name);
        setCurrentProcessingStep(1);

        const formData = new FormData();
        formData.append("file", file);
        if (templateIdToUse) {
          formData.append("template_id", templateIdToUse);
        }

        // Upload returns 202 as soon as the recording is stored; the actual
        // transcription runs in a worker and may be queued behind a provider
        // rate limit. Poll the real status instead of guessing with timers.
        const created: any = await apiFetch(
          `/transcripts/upload-audio?auto_analyze=${autoAnalyze}`,
          { method: "POST", body: formData }
        );
        setCurrentProcessingStep(2);

        lastCreatedTranscript = await waitForTranscription(created.id, (status) => {
          if (status === "transcribing") setCurrentProcessingStep(2);
          else if (status === "transcribed" || status === "completed")
            setCurrentProcessingStep(3);
        });
      }

      return lastCreatedTranscript;
    },
    onSuccess: (lastCreatedTranscript: any) => {
      setCurrentProcessingStep(4);
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      queryClient.invalidateQueries({ queryKey: ["analysis-runs"] });
      // Navigate first, then tear down the modal. Closing it before the route
      // change left the transcripts list visible for a beat, which read as the
      // app flashing an unrelated screen between "done" and the report.
      if (lastCreatedTranscript?.id) {
        router.push(`/transcripts/${lastCreatedTranscript.id}`);
      }
      closeModal();
    },
    onError: (err: any) => {
      setUploadError(err.message || "Upload error");
      setCurrentProcessingStep(0);
    },
  });

  const deleteTranscriptMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/transcripts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      setTranscriptToDelete(null);
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async () => {
      let succeeded = 0;
      const failed: string[] = [];
      for (const id of selectedIds) {
        try {
          await apiFetch(`/transcripts/${id}`, { method: "DELETE" });
          succeeded++;
        } catch {
          failed.push(id);
        }
      }
      return { succeeded, failed, total: selectedIds.length };
    },
    onSuccess: ({ succeeded, failed, total }) => {
      queryClient.invalidateQueries({ queryKey: ["transcripts"] });
      setSelectedIds(failed);
      if (failed.length === 0) {
        setIsBulkDeleteModalOpen(false);
        setBulkDeleteResult("");
      } else {
        setBulkDeleteResult(`${succeeded} of ${total} deleted, ${failed.length} failed.`);
      }
    },
  });

  const closeModal = () => {
    setIsModalOpen(false);
    setRawText("");
    setSourceCallId("");
    setSelectedFiles([]);
    setSelectedUploadTemplateId("");
    setCurrentProcessingStep(0);
    setCurrentFileProcessingName("");
    setUploadError("");
  };

  // Robust Time & Date Filtering
  const filteredTranscripts = transcripts.filter((t) => {
    const matchesSearch =
      (t.source_call_id || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.raw_text || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.creator?.full_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.creator?.email || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.id.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (dateFilter === "today") {
      const createdLocalDate = new Date(t.created_at).toLocaleDateString();
      const todayLocalDate = new Date().toLocaleDateString();
      return createdLocalDate === todayLocalDate;
    }

    if (dateFilter === "yesterday") {
      const createdLocalDate = new Date(t.created_at).toLocaleDateString();
      const y = new Date();
      y.setDate(y.getDate() - 1);
      return createdLocalDate === y.toLocaleDateString();
    }

    if (dateFilter === "7days") {
      const createdTime = new Date(t.created_at).getTime();
      const now = new Date().getTime();
      const diffDays = (now - createdTime) / (1000 * 60 * 60 * 24);
      return diffDays <= 7;
    }

    if (dateFilter === "30days") {
      const createdTime = new Date(t.created_at).getTime();
      const now = new Date().getTime();
      const diffDays = (now - createdTime) / (1000 * 60 * 60 * 24);
      return diffDays <= 30;
    }

    if (dateFilter === "custom") {
      const tTime = new Date(t.created_at).getTime();
      const startMs = customStartDate ? new Date(`${customStartDate}T00:00:00`).getTime() : 0;
      const endMs = customEndDate ? new Date(`${customEndDate}T23:59:59`).getTime() : Infinity;
      return tTime >= startMs && tTime <= endMs;
    }

    return true;
  });

  // Selection Handlers
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === filteredTranscripts.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredTranscripts.map((t) => t.id));
    }
  };

  const handleExportReports = () => {
    const targetTranscriptIds =
      selectedIds.length > 0 ? selectedIds : filteredTranscripts.map((t) => t.id);

    const transcriptsMap: Record<string, any> = {};
    transcripts.forEach((t) => {
      transcriptsMap[t.id] = t;
    });

    const targetRuns = runs.filter((r) => targetTranscriptIds.includes(r.transcript_id));
    exportBulkRunsToCSV(targetRuns.length > 0 ? targetRuns : runs, transcriptsMap);
  };

  // Computed KPI statistics
  const totalAudioCalls = transcripts.filter((t) => t.audio_file_key || t.audio_duration_seconds).length;
  const completedRunsCount = runs.filter((r) => r.status === "done").length;
  const doneRuns = runs.filter((r) => r.status === "done" && typeof r.overall_score === "number");
  const avgOverallScore =
    doneRuns.length > 0
      ? Math.round(doneRuns.reduce((acc: number, curr: any) => acc + curr.overall_score, 0) / doneRuns.length)
      : null;

  const uniqueLanguagesSet = new Set<string>();
  transcripts.forEach((t) => {
    if (t.detected_language) {
      t.detected_language.split(",").forEach((l: string) => uniqueLanguagesSet.add(l.trim()));
    }
  });
  const languagesList = Array.from(uniqueLanguagesSet);

  return (
    <div className="page-transition mx-auto max-w-7xl px-4 sm:px-6 py-8 space-y-8">
      {/* Delete Confirmation Modal using Portal */}
      <Modal isOpen={!!transcriptToDelete} onClose={() => setTranscriptToDelete(null)}>
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
              onClick={() => setTranscriptToDelete(null)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={deleteTranscriptMutation.isPending}
              onClick={() => deleteTranscriptMutation.mutate(transcriptToDelete.id)}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 shadow-xs disabled:opacity-50"
            >
              {deleteTranscriptMutation.isPending ? "Deleting..." : "Delete Transcript"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Bulk Delete Confirmation Modal using Portal */}
      <Modal isOpen={isBulkDeleteModalOpen} onClose={() => setIsBulkDeleteModalOpen(false)}>
        <div className="mx-auto max-w-md rounded-2xl border border-rose-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-rose-600">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <h3 className="text-lg font-bold text-slate-900">Delete Selected Transcripts?</h3>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            Are you sure you want to delete <strong className="text-slate-900">{selectedIds.length} selected transcript(s)</strong> and all associated evaluation runs? This action cannot be undone.
          </p>

          {bulkDeleteResult && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-semibold">
              {bulkDeleteResult}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => {
                setIsBulkDeleteModalOpen(false);
                setBulkDeleteResult("");
              }}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={bulkDeleteMutation.isPending}
              onClick={() => bulkDeleteMutation.mutate()}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 shadow-xs disabled:opacity-50 flex items-center gap-1.5"
            >
              {bulkDeleteMutation.isPending ? "Deleting..." : `Delete ${selectedIds.length} Transcripts`}
            </button>
          </div>
        </div>
      </Modal>

      {/* Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Call Transcripts & Quality Reports
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Enterprise call recording intelligence, multi-language STT, and AI scorecard analytics
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3 w-full sm:w-auto">
          <button
            onClick={handleExportReports}
            disabled={filteredTranscripts.length === 0}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-800 shadow-xs hover:border-teal-500 hover:text-teal-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-slate-200 disabled:hover:text-slate-800 w-full sm:w-auto"
          >
            <Download className="h-4 w-4 text-emerald-600" />
            {selectedIds.length > 0
              ? `Export Selected (${selectedIds.length})`
              : "Export Reports"}
          </button>

          {canUpload && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center justify-center gap-2 rounded-xl bg-teal-600 px-4.5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-teal-700 transition-all w-full sm:w-auto"
            >
              <Plus className="h-4 w-4" /> Upload Call Audio / Text
            </button>
          )}
        </div>
      </div>

      {/* Selection & Search Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={selectAll}
            className="flex items-center gap-2 text-xs font-bold text-slate-700 hover:text-slate-900"
          >
            {selectedIds.length > 0 && selectedIds.length === filteredTranscripts.length ? (
              <CheckSquare className="h-4 w-4 text-teal-600" />
            ) : (
              <Square className="h-4 w-4 text-slate-400" />
            )}
            Select All ({filteredTranscripts.length})
          </button>

          {selectedIds.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200">
                {selectedIds.length} Selected
              </span>

              {canDelete && (
                <button
                  onClick={() => setIsBulkDeleteModalOpen(true)}
                  className="flex items-center gap-1 text-xs font-bold text-rose-600 bg-rose-50 border border-rose-200 px-3 py-1 rounded-lg hover:bg-rose-600 hover:text-white transition-all shadow-xs"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete Selected ({selectedIds.length})
                </button>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Live Search */}
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search call ID, evaluator or text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full sm:w-64 rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
            />
          </div>

          {/* Date & Time Range Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Calendar className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value as any)}
                className="rounded-xl border border-slate-200 bg-slate-100 pl-8 pr-8 py-1.5 text-xs font-bold text-slate-800 appearance-none focus:border-teal-500 focus:outline-none cursor-pointer shadow-2xs"
              >
                <option value="all">All Time</option>
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="7days">Last 7 Days</option>
                <option value="30days">Last 30 Days</option>
                <option value="custom">Custom Date Range...</option>
              </select>
              <ChevronDown className="absolute right-2.5 top-2.5 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            </div>


            {/* Custom Date Inputs when Custom is selected */}
            {dateFilter === "custom" && (
              <div className="flex flex-wrap items-center gap-1.5 text-xs animate-in fade-in duration-200">
                <input
                  type="date"
                  value={customStartDate}
                  onChange={(e) => setCustomStartDate(e.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold text-slate-800 focus:border-teal-500 focus:outline-none"
                />
                <span className="text-slate-400 font-bold">to</span>
                <input
                  type="date"
                  value={customEndDate}
                  onChange={(e) => setCustomEndDate(e.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold text-slate-800 focus:border-teal-500 focus:outline-none"
                />
                {(customStartDate || customEndDate) && (
                  <button
                    onClick={() => {
                      setCustomStartDate("");
                      setCustomEndDate("");
                    }}
                    className="text-slate-400 hover:text-rose-600 p-1"
                    title="Clear custom date range"
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          </div>



          {/* View Mode Switcher */}
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-lg transition-all ${
                viewMode === "grid" ? "bg-white text-teal-700 shadow-2xs" : "text-slate-500 hover:text-slate-900"
              }`}
              title="Grid Cards View"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded-lg transition-all ${
                viewMode === "table" ? "bg-white text-teal-700 shadow-2xs" : "text-slate-500 hover:text-slate-900"
              }`}
              title="Compact Table View"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Audio & Text Upload Modal using Portal */}
      <Modal isOpen={isModalOpen} onClose={closeModal}>
        <div className="mx-auto w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-2xl space-y-6">
          {uploadAudioMutation.isPending ? (
            /* Executive Real-Time Audio Processing Loader */
            <div className="py-6 text-center space-y-6">
              <div className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-50 border border-teal-200 text-teal-600">
                <Cpu className="h-8 w-8 animate-pulse" />
                <Loader2 className="absolute inset-0 h-16 w-16 text-teal-600/30 animate-spin" />
              </div>

              <div>
                <h3 className="text-lg font-extrabold text-slate-900">
                  Processing Audio Call File
                </h3>
                <p className="mt-1 text-xs text-slate-500 font-mono font-medium truncate max-w-sm mx-auto">
                  {currentFileProcessingName || "Uploaded audio recording"}
                </p>
              </div>

              {/* Real-time Processing Steps Progress Bar */}
              <div className="space-y-3 bg-slate-50 p-4 rounded-2xl border border-slate-200 text-left">
                {/* Step 1 */}
                <div className="flex items-center gap-3 text-xs font-bold">
                  <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${currentProcessingStep >= 1 ? "bg-teal-600 text-white" : "bg-slate-200 text-slate-500"}`}>
                    {currentProcessingStep > 1 ? <CheckCircle2 className="h-3.5 w-3.5" /> : "1"}
                  </span>
                  <span className={currentProcessingStep === 1 ? "text-teal-700 font-bold" : currentProcessingStep > 1 ? "text-slate-900 font-semibold" : "text-slate-400"}>
                    Uploading Audio Recording
                  </span>
                </div>

                {/* Step 2 */}
                <div className="flex items-center gap-3 text-xs font-bold">
                  <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${currentProcessingStep >= 2 ? "bg-teal-600 text-white" : "bg-slate-200 text-slate-500"}`}>
                    {currentProcessingStep > 2 ? <CheckCircle2 className="h-3.5 w-3.5" /> : "2"}
                  </span>
                  <span className={currentProcessingStep === 2 ? "text-teal-700 font-bold" : currentProcessingStep > 2 ? "text-slate-900 font-semibold" : "text-slate-400"}>
                    Speech-to-Text Transcription via Whisper STT
                  </span>
                </div>

                {/* Step 3: Conditional based on autoAnalyze checkbox */}
                <div className="flex items-center gap-3 text-xs font-bold">
                  <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${currentProcessingStep >= 3 ? "bg-teal-600 text-white" : "bg-slate-200 text-slate-500"}`}>
                    {currentProcessingStep >= 4 ? <CheckCircle2 className="h-3.5 w-3.5" /> : "3"}
                  </span>
                  <span className={currentProcessingStep >= 3 ? "text-teal-700 font-bold" : "text-slate-400"}>
                    {autoAnalyze
                      ? "Speaker Turn Diarization & AI Scorecard Evaluation"
                      : "Speaker Turn Diarization & Role Labeling"}
                  </span>
                </div>
              </div>

              <p className="text-[11px] font-medium text-slate-400">
                {autoAnalyze
                  ? "Please hold on, your audio call is being transcribed and scored automatically..."
                  : "Please hold on, your audio call is being transcribed and diarized..."}
              </p>
            </div>
          ) : (
            /* Upload Form Modal Body */
            <>
              {uploadError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-semibold">
                  {uploadError}
                </div>
              )}

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-4">
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <UploadCloud className="h-5 w-5 text-teal-600" /> Upload Call File
                </h2>

                <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs">
                  <button
                    type="button"
                    onClick={() => setUploadMode("audio")}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                      uploadMode === "audio"
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <Mic className="h-3.5 w-3.5" /> Audio File
                  </button>
                  <button
                    type="button"
                    onClick={() => setUploadMode("text")}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                      uploadMode === "text"
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <FileCode className="h-3.5 w-3.5" /> Paste Text
                  </button>
                </div>
              </div>

              {uploadMode === "audio" ? (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-center">
                    <Mic className="mx-auto h-8 w-8 text-teal-600 mb-2" />
                    <p className="text-xs font-bold text-slate-900">
                      Select audio call files (.mp3, .wav, .m4a, .ogg, .flac)
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5 font-medium">
                      Automatic Speech-to-Text transcription & quality evaluation
                    </p>
                    <input
                      type="file"
                      multiple
                      accept="audio/*"
                      onChange={(e) => {
                        if (e.target.files) {
                          const fileList = Array.from(e.target.files).slice(0, 5);
                          setSelectedFiles(fileList);
                        }
                      }}
                      className="mt-4 text-xs text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-slate-900 file:text-white hover:file:bg-slate-800 cursor-pointer"
                    />

                    {selectedFiles.length > 0 && (
                      <div className="mt-3 text-left bg-white p-3.5 rounded-xl border border-slate-200 space-y-1 shadow-2xs">
                        <p className="text-[11px] font-bold text-slate-800">
                          {selectedFiles.length} File(s) Selected:
                        </p>
                        {selectedFiles.map((f, i) => (
                          <p key={i} className="text-[10px] text-slate-600 font-mono truncate">
                            • {f.name} ({Math.round(f.size / 1024)} KB)
                          </p>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Scorecard Template Selector */}
                  {templates.length > 0 && (
                    <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2">
                      <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Evaluation Scorecard</p>
                      {templates.length === 1 ? (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 border border-teal-200 px-2 py-0.5 text-[10px] font-bold text-teal-700">
                            ★ Active
                          </span>
                          <span className="font-semibold text-slate-900">{activeTemplate?.name}</span>
                          {activeTemplate?.version && (
                            <span className="text-slate-400 font-mono text-[10px]">v{activeTemplate.version}</span>
                          )}
                        </div>
                      ) : (
                        <div className="relative">
                          <select
                            value={selectedUploadTemplateId || activeTemplate?.id || ""}
                            onChange={(e) => setSelectedUploadTemplateId(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-800 focus:border-teal-500 focus:outline-none appearance-none cursor-pointer"
                          >
                            {templates.map((tpl) => (
                              <option key={tpl.id} value={tpl.id}>
                                {tpl.name} (v{tpl.version}){tpl.is_active ? " ★ Default" : ""}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-slate-900">
                    <input
                      type="checkbox"
                      id="autoAnalyze"
                      checked={autoAnalyze}
                      onChange={(e) => setAutoAnalyze(e.target.checked)}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                    <label htmlFor="autoAnalyze" className="cursor-pointer font-semibold">
                      Automatically run AI scorecard evaluation after transcription
                    </label>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700">
                      Call Reference / Source ID (Optional)
                    </label>
                    <input
                      type="text"
                      value={sourceCallId}
                      onChange={(e) => setSourceCallId(e.target.value)}
                      placeholder="CALL-89472"
                      className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700">
                      Raw Transcript Text
                    </label>
                    <textarea
                      rows={6}
                      required
                      value={rawText}
                      onChange={(e) => setRawText(e.target.value)}
                      placeholder="Paste full call transcript here..."
                      className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
                >
                  Cancel
                </button>
                {uploadMode === "audio" ? (
                  <button
                    type="button"
                    disabled={uploadAudioMutation.isPending || selectedFiles.length === 0}
                    onClick={() => uploadAudioMutation.mutate()}
                    className="rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5"
                  >
                    Process & Evaluate ({selectedFiles.length})
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={uploadTextMutation.isPending || !rawText.trim()}
                    onClick={() =>
                      uploadTextMutation.mutate({
                        raw_text: rawText,
                        source_call_id: sourceCallId || undefined,
                      })
                    }
                    className="rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-teal-700 disabled:opacity-50"
                  >
                    {uploadTextMutation.isPending ? "Submitting..." : "Submit Transcript"}
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* ── TRANSCRIPTS LIST / GRID ─────────────────────────────────── */}
      {isLoading ? (
        <TranscriptsSkeleton />
      ) : filteredTranscripts.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-xs space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-50 text-teal-600 border border-teal-100">
            <FileText className="h-8 w-8" />
          </div>
          <h3 className="text-base font-extrabold text-slate-900">No Transcripts Found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Upload audio call files or paste raw text transcripts to analyze call performance and compliance scores.
          </p>
          {canUpload && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-teal-600 text-white font-bold px-5 py-2.5 text-xs shadow-md hover:bg-teal-700 transition-all"
            >
              <Plus className="h-4 w-4" /> Upload Call Audio / Text
            </button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        /* ── RICH GRID CARDS VIEW ──────────────────────────────────── */
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredTranscripts.map((t) => {
            const isSelected = selectedIds.includes(t.id);
            const transcriptRuns = runs.filter((r) => r.transcript_id === t.id);
            const latestRun = transcriptRuns[transcriptRuns.length - 1];
            const hasAudio = !!(t.audio_file_key || t.audio_duration_seconds);

            // Format audio duration
            const formatDuration = (sec?: number) => {
              if (!sec) return null;
              const m = Math.floor(sec / 60);
              const s = Math.floor(sec % 60);
              return `${m}:${s < 10 ? "0" : ""}${s}`;
            };

            const langList = t.detected_language
              ? t.detected_language.split(",").map((l: string) => l.trim())
              : [];

            return (
              <div
                key={t.id}
                onClick={() => router.push(`/transcripts/${t.id}`)}
                className={`group relative flex flex-col justify-between rounded-3xl border p-4 sm:p-6 transition-all cursor-pointer shadow-xs hover:shadow-xl ${
                  isSelected
                    ? "border-teal-500 bg-teal-50/20 ring-2 ring-teal-500/30"
                    : "border-slate-200 bg-white hover:border-teal-400"
                }`}
              >
                <div className="space-y-4">
                  {/* Top Card Header */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelect(t.id);
                        }}
                        className="p-1 rounded-md hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-900 shrink-0"
                        title={isSelected ? "Deselect transcript" : "Select transcript"}
                      >
                        {isSelected ? (
                          <CheckSquare className="h-4 w-4 text-teal-600" />
                        ) : (
                          <Square className="h-4 w-4 text-slate-300" />
                        )}
                      </button>

                      <div className="flex items-center gap-1.5 min-w-0">
                        <PhoneCall className="h-3.5 w-3.5 text-teal-600 shrink-0" />
                        <span className="font-mono text-xs font-bold text-slate-900 truncate max-w-[140px] sm:max-w-none">
                          {t.source_call_id || `CALL-${t.id.substring(0, 8).toUpperCase()}`}
                        </span>
                      </div>
                    </div>

                    {/* Latest Score Badge */}
                    {latestRun && latestRun.status === "done" && typeof latestRun.overall_score === "number" ? (
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] sm:text-[11px] font-extrabold shadow-2xs shrink-0 ${
                          latestRun.overall_score >= 80
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : latestRun.overall_score >= 60
                            ? "bg-amber-100 text-amber-800 border border-amber-300"
                            : "bg-rose-100 text-rose-800 border border-rose-300"
                        }`}
                      >
                        {latestRun.overall_score >= 80 ? (
                          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                        ) : (
                          <AlertCircle className="h-3 w-3 text-amber-600" />
                        )}
                        {Math.round(latestRun.overall_score * 10) / 10}%
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-[9px] sm:text-[10px] font-bold text-slate-500 uppercase tracking-wider shrink-0">
                        {transcriptRuns.length > 0 ? `${transcriptRuns.length} Runs` : "New Call"}
                      </span>
                    )}
                  </div>

                  {/* Audio & Language Badges Row */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {hasAudio ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-teal-50 border border-teal-200 px-2 py-0.5 sm:px-2.5 sm:py-1 text-[10px] sm:text-[11px] font-bold text-teal-800">
                        <Mic className="h-3 w-3 sm:h-3.5 sm:w-3.5 text-teal-600" /> Audio
                        {formatDuration(t.audio_duration_seconds) && (
                          <span className="font-mono text-[9px] sm:text-[10px] text-teal-700">
                            ({formatDuration(t.audio_duration_seconds)})
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                        <FileText className="h-3 w-3 text-slate-400" /> Text Input
                      </span>
                    )}

                    {/* Language Badges */}
                    {langList.map((lang: string, idx: number) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 border border-indigo-200 px-2 py-0.5 sm:px-2 sm:py-1 text-[10px] font-bold text-indigo-800"
                      >
                        <Globe className="h-3 w-3 text-indigo-600" /> {lang}
                      </span>
                    ))}
                  </div>

                  {/* Dialogue Snippet Preview Box */}
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3 space-y-1 group-hover:bg-teal-50/20 group-hover:border-teal-100 transition-colors">
                    <p className="text-xs text-slate-700 line-clamp-3 leading-relaxed font-medium break-words">
                      &quot;{t.raw_text}&quot;
                    </p>
                  </div>
                </div>

                {/* Footer Meta & Actions */}
                <div
                  className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-1 text-[10px] font-medium text-slate-500">
                      <Calendar className="h-3 w-3 text-slate-400 shrink-0" />
                      {new Date(t.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </div>
                    {t.creator && (
                      <div className="flex items-center gap-1 text-[10px] font-bold text-indigo-700 truncate max-w-[100px]">
                        <UserCheck className="h-3 w-3 text-indigo-600 shrink-0" />
                        {t.creator.full_name || t.creator.email.split("@")[0]}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {canDelete && (
                      <button
                        onClick={() => setTranscriptToDelete(t)}
                        className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        title="Delete Transcript"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}

                    <Link
                      href={`/transcripts/${t.id}`}
                      className="flex items-center gap-1 rounded-xl bg-white border border-slate-200 px-2.5 py-1.5 text-xs font-bold text-slate-900 shadow-2xs hover:border-teal-500 hover:text-teal-600 hover:bg-teal-50 transition-all shrink-0"
                    >
                      View Report <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* ── COMPACT TABLE VIEW ────────────────────────────────────── */
        <div className="rounded-3xl border border-slate-200 bg-white overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="p-4 w-10">Select</th>
                  <th className="p-4">Call Reference ID</th>
                  <th className="p-4">Type & Languages</th>
                  <th className="p-4">Latest Score</th>
                  <th className="p-4">Runs</th>
                  <th className="p-4">Uploaded Date</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredTranscripts.map((t) => {
                  const isSelected = selectedIds.includes(t.id);
                  const transcriptRuns = runs.filter((r) => r.transcript_id === t.id);
                  const latestRun = transcriptRuns[transcriptRuns.length - 1];

                  return (
                    <tr
                      key={t.id}
                      onClick={() => router.push(`/transcripts/${t.id}`)}
                      className={`cursor-pointer hover:bg-teal-50/30 transition-colors ${
                        isSelected ? "bg-teal-50/20" : ""
                      }`}
                    >
                      <td className="p-4" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => toggleSelect(t.id)}
                          className="p-1 rounded-md text-slate-400 hover:text-slate-900"
                        >
                          {isSelected ? (
                            <CheckSquare className="h-4 w-4 text-teal-600" />
                          ) : (
                            <Square className="h-4 w-4 text-slate-300" />
                          )}
                        </button>
                      </td>
                      <td className="p-4">
                        <div className="font-mono font-bold text-slate-900 flex items-center gap-2">
                          <PhoneCall className="h-3.5 w-3.5 text-teal-600" />
                          {t.source_call_id || `CALL-${t.id.substring(0, 8).toUpperCase()}`}
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-bold text-slate-700 text-[10px]">
                            {t.audio_file_key ? "Audio Call" : "Text"}
                          </span>
                          {t.detected_language && (
                            <span className="rounded-md bg-indigo-50 border border-indigo-200 px-2 py-0.5 font-bold text-indigo-800 text-[10px]">
                              {t.detected_language}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        {latestRun && latestRun.status === "done" && typeof latestRun.overall_score === "number" ? (
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-extrabold ${
                              latestRun.overall_score >= 80
                                ? "bg-emerald-100 text-emerald-800"
                                : latestRun.overall_score >= 60
                                ? "bg-amber-100 text-amber-800"
                                : "bg-rose-100 text-rose-800"
                            }`}
                          >
                            {Math.round(latestRun.overall_score * 10) / 10}%
                          </span>
                        ) : (
                          <span className="text-slate-400 font-medium">—</span>
                        )}
                      </td>
                      <td className="p-4 font-bold text-slate-600">{transcriptRuns.length}</td>
                      <td className="p-4 text-slate-500 font-medium">
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td className="p-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          {canDelete && (
                            <button
                              onClick={() => setTranscriptToDelete(t)}
                              className="p-1 text-slate-400 hover:text-rose-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                          <Link
                            href={`/transcripts/${t.id}`}
                            className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-1 text-xs font-bold text-slate-800 hover:border-teal-500 hover:text-teal-600"
                          >
                            View
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
