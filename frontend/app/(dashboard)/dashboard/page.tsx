"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatToUserLocalTime } from "@/lib/date-utils";
import {
  Activity,
  Sliders,
  FileText,
  Plus,
  ArrowUpRight,
  Clock,
  CheckCircle2,
  TrendingUp,
  BarChart2,
  Check,
  Search,
  Filter,
  Sparkles,
  AlertTriangle,
  Award,
  Layers,
  ChevronLeft,
  ChevronRight,
  XCircle,
} from "lucide-react";

import { DashboardSkeleton } from "@/components/DashboardSkeleton";

export default function DashboardPage() {
  const { user, organization } = useAuth();
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(5);

  const { data: templates = [], isLoading: templatesLoading } = useQuery<any[]>({
    queryKey: ["templates"],
    queryFn: () => apiFetch("/templates"),
  });

  const { data: transcripts = [], isLoading: transcriptsLoading } = useQuery<any[]>({
    queryKey: ["transcripts"],
    queryFn: () => apiFetch("/transcripts"),
  });

  const { data: runs = [], isLoading: runsLoading } = useQuery<any[]>({
    queryKey: ["analysis-runs"],
    queryFn: () => apiFetch("/analysis-runs"),
  });

  const isLoading = templatesLoading || transcriptsLoading || runsLoading;

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  const activeTemplate = templates.find((t) => t.is_active);
  const completedRuns = runs.filter((r) => r.status === "done");
  const failedRuns = runs.filter((r) => r.status === "failed");

  // Performance Breakdown
  const highScoringRuns = completedRuns.filter((r) => (r.overall_score || 0) >= 80);
  const avgScoringRuns = completedRuns.filter((r) => (r.overall_score || 0) >= 60 && (r.overall_score || 0) < 80);
  const lowScoringRuns = completedRuns.filter((r) => (r.overall_score || 0) < 60);

  const avgScoreNum =
    completedRuns.length > 0
      ? completedRuns.reduce((acc, r) => acc + (r.overall_score || 0), 0) /
        completedRuns.length
      : null;

  const avgScoreStr = avgScoreNum !== null ? `${avgScoreNum.toFixed(1)}%` : "N/A";

  // Filtered runs based on search and status tabs
  const filteredRuns = runs.filter((run) => {
    const matchedTpl = templates.find((t) => t.id === run.template_id);
    const tplName = matchedTpl ? matchedTpl.name : run.template_name || "";
    const matchesSearch =
      run.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tplName.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (filterStatus === "completed") return run.status === "done";
    if (filterStatus === "failed") return run.status === "failed";
    if (filterStatus === "high") return run.status === "done" && (run.overall_score || 0) >= 80;
    if (filterStatus === "satisfactory") return run.status === "done" && (run.overall_score || 0) >= 60 && (run.overall_score || 0) < 80;
    if (filterStatus === "needs_attention") return run.status === "done" && (run.overall_score || 0) < 60;
    return true;
  });

  // Paginated Sliced Runs
  const totalFilteredCount = filteredRuns.length;
  const totalPages = Math.max(1, Math.ceil(totalFilteredCount / pageSize));
  const paginatedRuns = filteredRuns.slice((page - 1) * pageSize, page * pageSize);

  const handleDistributionClick = (statusKey: string) => {
    setFilterStatus(statusKey);
    setPage(1);
    const el = document.getElementById("runs-explorer-table");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="page-transition max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-8 space-y-6 sm:space-y-8 overflow-x-hidden">
      {/* Interactive Command Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-5 sm:pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-900 px-2.5 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
              {organization?.name || "Workspace"}
            </span>
            <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[10px] font-bold text-teal-700 border border-teal-200 flex items-center gap-1">
              <Sparkles className="h-3 w-3" /> Live Operations
            </span>
          </div>
          <h1 className="mt-2 text-xl sm:text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
            Call Quality Command Center
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500 max-w-full leading-normal">
            Interactive evaluation metrics, score distributions, and real-time call performance
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3 w-full sm:w-auto">
          <Link
            href="/transcripts"
            className="flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4.5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-slate-800 transition-all w-full sm:w-auto"
          >
            <Plus className="h-4 w-4" /> Upload Call Input
          </Link>
        </div>
      </div>

      {/* Overview Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* Active Scorecard Framework */}
        <Link
          href="/templates"
          className="group rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs hover:border-teal-400 hover:shadow-md transition-all space-y-3"
        >
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
              Active Scorecard
            </span>
            <Sliders className="h-4 w-4 text-slate-400 group-hover:text-teal-600 transition-colors" />
          </div>
          <div>
            <p className="text-base sm:text-lg font-extrabold text-slate-900 line-clamp-1">
              {activeTemplate ? activeTemplate.name : "QA Master Framework"}
            </p>
            <p className="mt-0.5 text-xs text-slate-500 font-medium">
              Version {activeTemplate?.version || 1} ({activeTemplate?.parameters?.length || 59} parameters)
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="font-semibold text-emerald-700 flex items-center gap-1">
              <Check className="h-3.5 w-3.5" /> Default Active
            </span>
            <span className="font-bold text-slate-900 group-hover:underline">Manage →</span>
          </div>
        </Link>

        {/* Total Transcripts Card */}
        <Link
          href="/transcripts"
          className="group rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs hover:border-slate-400 hover:shadow-md transition-all space-y-3"
        >
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
              Total Transcripts
            </span>
            <FileText className="h-4 w-4 text-slate-400 group-hover:text-slate-900 transition-colors" />
          </div>
          <div>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900">{transcripts.length}</p>
            <p className="mt-1 text-xs text-slate-500 font-medium">
              Audio files & call logs
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="font-semibold text-slate-500">
              {transcripts.filter((t) => t.audio_file_key || t.audio_duration_seconds).length} Audio Files
            </span>
            <span className="font-bold text-slate-900 group-hover:underline">Browse →</span>
          </div>
        </Link>

        {/* Total Runs Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
              Evaluations Executed
            </span>
            <CheckCircle2 className="h-4 w-4 text-slate-400" />
          </div>
          <div>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900">{runs.length}</p>
            <p className="mt-1 text-xs text-slate-500 font-medium">Scorecard runs</p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="font-semibold text-emerald-700">
              {completedRuns.length} Completed
            </span>
            {failedRuns.length > 0 && (
              <span className="font-semibold text-rose-600">
                {failedRuns.length} Failed
              </span>
            )}
          </div>
        </div>

        {/* Average Score Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
              Average Call Score
            </span>
            <TrendingUp className="h-4 w-4 text-slate-400" />
          </div>
          <div>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {avgScoreStr}
            </p>
            <p className="mt-1 text-xs text-slate-500 font-medium">
              Overall quality compliance
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="font-bold text-slate-700 flex items-center gap-1 truncate">
              <BarChart2 className="h-3.5 w-3.5 text-slate-500 shrink-0" />
              <span className="truncate">
                {avgScoreNum !== null && avgScoreNum >= 80
                  ? "Excellent Grade"
                  : avgScoreNum !== null && avgScoreNum >= 60
                  ? "Satisfactory Grade"
                  : "Needs Review"}
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* Interactive Quality Score Distribution Widget */}
      {completedRuns.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-slate-100 pb-3">
            <h2 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-slate-600 shrink-0" /> Call Performance Distribution
            </h2>
            <span className="text-[10px] sm:text-xs font-semibold text-slate-500">
              Click any bar to filter evaluation runs below ({completedRuns.length} Evaluated Calls)
            </span>
          </div>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
            <div
              onClick={() => handleDistributionClick("high")}
              title="Click to filter table below by High (80%+) calls"
              className={`cursor-pointer rounded-xl p-3.5 border transition-all ${
                filterStatus === "high"
                  ? "bg-emerald-50 border-emerald-300 ring-2 ring-emerald-500/20 shadow-xs"
                  : "bg-slate-50 border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/40"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-bold text-emerald-800">
                <span className="flex items-center gap-1.5 truncate">
                  <Award className="h-4 w-4 text-emerald-600 shrink-0" /> High (80%+)
                </span>
                <span>{highScoringRuns.length}</span>
              </div>
              <div className="mt-2.5 h-2 w-full rounded-full bg-emerald-200/60 overflow-hidden">
                <div
                  className="h-full bg-emerald-600 rounded-full transition-all duration-500"
                  style={{
                    width: `${completedRuns.length > 0 ? (highScoringRuns.length / completedRuns.length) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>

            <div
              onClick={() => handleDistributionClick("satisfactory")}
              title="Click to filter table below by Satisfactory (60-79%) calls"
              className={`cursor-pointer rounded-xl p-3.5 border transition-all ${
                filterStatus === "satisfactory"
                  ? "bg-amber-50 border-amber-300 ring-2 ring-amber-500/20 shadow-xs"
                  : "bg-slate-50 border-slate-200 hover:border-amber-300 hover:bg-amber-50/40"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-bold text-amber-800">
                <span className="flex items-center gap-1.5 truncate">
                  <CheckCircle2 className="h-4 w-4 text-amber-600 shrink-0" /> Satisfactory (60-79%)
                </span>
                <span>{avgScoringRuns.length}</span>
              </div>
              <div className="mt-2.5 h-2 w-full rounded-full bg-amber-200/60 overflow-hidden">
                <div
                  className="h-full bg-amber-600 rounded-full transition-all duration-500"
                  style={{
                    width: `${completedRuns.length > 0 ? (avgScoringRuns.length / completedRuns.length) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>

            <div
              onClick={() => handleDistributionClick("needs_attention")}
              title="Click to filter table below by Needs Attention (<60%) calls"
              className={`cursor-pointer rounded-xl p-3.5 border transition-all ${
                filterStatus === "needs_attention"
                  ? "bg-rose-50 border-rose-300 ring-2 ring-rose-500/20 shadow-xs"
                  : "bg-slate-50 border-slate-200 hover:border-rose-300 hover:bg-rose-50/40"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-bold text-rose-800">
                <span className="flex items-center gap-1.5 truncate">
                  <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" /> Needs Attention (&lt;60%)
                </span>
                <span>{lowScoringRuns.length}</span>
              </div>
              <div className="mt-2.5 h-2 w-full rounded-full bg-rose-200/60 overflow-hidden">
                <div
                  className="h-full bg-rose-600 rounded-full transition-all duration-500"
                  style={{
                    width: `${completedRuns.length > 0 ? (lowScoringRuns.length / completedRuns.length) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Recent Evaluation Runs Table with Live Filter & Pagination */}
      <div id="runs-explorer-table" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-4 scroll-mt-20">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
              <Clock className="h-4.5 w-4.5 text-slate-500 shrink-0" /> Evaluation Runs Explorer ({totalFilteredCount})
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Filter by score grade or search by scorecard template name
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3">
            {/* Live Search Input */}
            <div className="relative w-full sm:w-56">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search run ID or scorecard..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-slate-400 focus:outline-none"
              />
            </div>

            {/* Filter Tabs */}
            <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs justify-between sm:justify-start">
              <button
                onClick={() => {
                  setFilterStatus("all");
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  filterStatus === "all" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                All
              </button>
              <button
                onClick={() => {
                  setFilterStatus("completed");
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  filterStatus === "completed" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Done
              </button>
              <button
                onClick={() => {
                  setFilterStatus("high");
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  filterStatus === "high" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                80%+
              </button>
              <button
                onClick={() => {
                  setFilterStatus("needs_attention");
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  filterStatus === "needs_attention" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                &lt;60%
              </button>
            </div>
          </div>
        </div>

        {filteredRuns.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50 space-y-3">
            <Filter className="mx-auto h-8 w-8 text-slate-400" />
            <div>
              <p className="text-xs font-bold text-slate-800">No evaluation runs match your filters</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Try resetting your search query or selecting &quot;All&quot; filter tab.
              </p>
            </div>
            <button
              onClick={() => {
                setFilterStatus("all");
                setSearchQuery("");
                setPage(1);
              }}
              className="inline-flex items-center gap-1 text-xs font-bold text-slate-900 hover:underline"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* MOBILE CARDS (< md) */}
            <div className="block md:hidden space-y-3">
              {paginatedRuns.map((run) => {
                const matchedTpl = templates.find((t) => t.id === run.template_id);
                const tplName = matchedTpl
                  ? `${matchedTpl.name} (v${run.template_version})`
                  : (run.template_name ? `${run.template_name} (v${run.template_version})` : `Scorecard (v${run.template_version})`);

                return (
                  <div
                    key={run.id}
                    className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 space-y-2.5 shadow-2xs hover:bg-slate-100/70 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2 border-b border-slate-200/60 pb-2">
                      <span className="font-mono text-xs font-bold text-slate-600">
                        ID: {run.id.substring(0, 8)}...
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          run.status === "done"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : run.status === "failed"
                            ? "bg-rose-50 text-rose-700 border border-rose-200"
                            : "bg-slate-100 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {run.status}
                      </span>
                    </div>

                    <div>
                      <p className="text-xs font-bold text-slate-900">{tplName}</p>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        Date: {new Date(run.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center justify-between bg-white rounded-lg p-2 border border-slate-200 pt-2">
                      <div>
                        <span className="text-[10px] text-slate-500 block">Quality Score</span>
                        {run.overall_score !== null ? (
                          <span className={`text-base font-black ${run.overall_score >= 80 ? "text-emerald-700" : run.overall_score >= 60 ? "text-slate-900" : "text-rose-700"}`}>
                            {run.overall_score.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-400 text-sm font-bold">-</span>
                        )}
                      </div>

                      <Link
                        href={`/analysis-runs/${run.id}`}
                        className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-slate-800 transition-all shadow-2xs"
                      >
                        View Scorecard <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* DESKTOP TABLE (>= md) */}
            <div className="hidden md:block overflow-x-auto scrollbar-thin">
              <table className="w-full text-left text-xs min-w-[650px]">
                <thead className="border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-wider font-bold bg-slate-50">
                  <tr>
                    <th className="py-3 px-4">Run ID</th>
                    <th className="py-3 px-4">Scorecard Template</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Quality Score</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-900">
                  {paginatedRuns.map((run) => {
                    const matchedTpl = templates.find((t) => t.id === run.template_id);
                    const tplName = matchedTpl
                      ? `${matchedTpl.name} (v${run.template_version})`
                      : (run.template_name ? `${run.template_name} (v${run.template_version})` : `Scorecard Template (v${run.template_version})`);

                    return (
                      <tr key={run.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-slate-500 whitespace-nowrap">
                          {run.id.substring(0, 8)}...
                        </td>
                        <td className="py-3.5 px-4 font-bold text-slate-900">
                          {tplName}
                        </td>
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                              run.status === "done"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : run.status === "failed"
                                ? "bg-rose-50 text-rose-700 border border-rose-200"
                                : "bg-slate-100 text-slate-700 border border-slate-200"
                            }`}
                          >
                            {run.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-bold text-slate-900 text-sm whitespace-nowrap">
                          {run.overall_score !== null ? (
                            <span className={run.overall_score >= 80 ? "text-emerald-700 font-extrabold" : run.overall_score >= 60 ? "text-slate-900 font-bold" : "text-rose-700 font-extrabold"}>
                              {run.overall_score.toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-slate-400">-</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                          {new Date(run.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <Link
                            href={`/analysis-runs/${run.id}`}
                            className="inline-flex items-center gap-1 text-slate-900 hover:underline font-bold"
                          >
                            View Scorecard <ArrowUpRight className="h-3.5 w-3.5" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Footer */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2 text-xs text-slate-600 w-full sm:w-auto justify-between sm:justify-start">
                <span className="text-[11px]">Rows:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-bold text-slate-800 focus:outline-none cursor-pointer"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                </select>
                <span className="font-semibold text-slate-500 text-[11px] truncate">
                  {Math.min((page - 1) * pageSize + 1, totalFilteredCount)}-
                  {Math.min(page * pageSize, totalFilteredCount)} of {totalFilteredCount}
                </span>
              </div>

              {/* Prev / Next Buttons */}
              <div className="flex items-center justify-between sm:justify-end gap-2 w-full sm:w-auto pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed shadow-xs"
                >
                  <ChevronLeft className="h-4 w-4" /> Prev
                </button>
                <span className="px-2 text-xs font-bold text-slate-800">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed shadow-xs"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
