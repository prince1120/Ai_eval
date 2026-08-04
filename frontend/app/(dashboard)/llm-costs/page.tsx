"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatToUserLocalTime } from "@/lib/date-utils";
import { LLMCostsSkeleton } from "@/components/LLMCostsSkeleton";
import {
  DollarSign,
  Cpu,
  Zap,
  Activity,
  ShieldAlert,
  Search,
  Filter,
  Layers,
  Clock,
  CheckCircle2,
  XCircle,
  BarChart3,
  Server,
  Sparkles,
  UserCheck,
  FileText,
  ExternalLink,
  Mic,
  Calendar,
  ChevronLeft,
  ChevronRight,
  User,
} from "lucide-react";

export default function LLMCostsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [selectedDatePreset, setSelectedDatePreset] = useState<string>("all");

  // Pagination State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);

  // Fetch team members for Evaluator filter
  const { data: teamMembers = [] } = useQuery<any[]>({
    queryKey: ["team-members-cost-filter"],
    queryFn: () => apiFetch("/users"),
    enabled: isAdmin,
  });

  const { data: summary, isLoading: isLoadingSummary } = useQuery<any>({
    queryKey: ["llm-summary", selectedUserId, selectedDatePreset],
    queryFn: () => {
      const params = new URLSearchParams();
      if (selectedUserId) params.append("user_id", selectedUserId);
      if (selectedDatePreset && selectedDatePreset !== "all") params.append("date_preset", selectedDatePreset);
      const queryStr = params.toString();
      return apiFetch(`/analytics/llm-summary${queryStr ? `?${queryStr}` : ""}`);
    },
    enabled: isAdmin,
  });

  const { data: breakdown = [], isLoading: isLoadingBreakdown } = useQuery<any[]>({
    queryKey: ["llm-breakdown", selectedUserId, selectedDatePreset],
    queryFn: () => {
      const params = new URLSearchParams();
      if (selectedUserId) params.append("user_id", selectedUserId);
      if (selectedDatePreset && selectedDatePreset !== "all") params.append("date_preset", selectedDatePreset);
      const queryStr = params.toString();
      return apiFetch(`/analytics/llm-breakdown${queryStr ? `?${queryStr}` : ""}`);
    },
    enabled: isAdmin,
  });

  const { data: logs = [], isLoading: isLoadingLogs } = useQuery<any[]>({
    queryKey: ["llm-logs", selectedModel, selectedUserId, selectedDatePreset, page, pageSize],
    queryFn: () => {
      const offset = (page - 1) * pageSize;
      const params = new URLSearchParams();
      params.append("limit", pageSize.toString());
      params.append("offset", offset.toString());
      if (selectedModel) params.append("model_name", selectedModel);
      if (selectedUserId) params.append("user_id", selectedUserId);
      if (selectedDatePreset && selectedDatePreset !== "all") params.append("date_preset", selectedDatePreset);
      return apiFetch(`/analytics/llm-logs?${params.toString()}`);
    },
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 mb-4">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">Access Restricted</h2>
        <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto">
          LLM Cost & Token Analytics are strictly restricted to System Administrators (`admin` role).
        </p>
      </div>
    );
  }

  const isLoading = isLoadingSummary || isLoadingBreakdown || isLoadingLogs;

  if (isLoading) {
    return <LLMCostsSkeleton />;
  }

  const formatUsd = (val: number | undefined) => {
    if (val === undefined || val === null) return "$0.000000";
    return `$${val.toFixed(6)}`;
  };

  const formatNumber = (val: number | undefined) => {
    if (val === undefined || val === null) return "0";
    return val.toLocaleString();
  };

  const renderActionBadge = (action: string) => {
    switch (action) {
      case "stt_whisper_transcription":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
            <Mic className="h-3 w-3 text-amber-600" /> Audio STT (Whisper)
          </span>
        );
      case "speaker_diarization":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-[10px] font-bold text-purple-700 border border-purple-200">
            <Layers className="h-3 w-3 text-purple-600" /> Diarization
          </span>
        );
      case "scorecard_evaluation":
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-0.5 text-[10px] font-bold text-teal-700 border border-teal-200">
            <Activity className="h-3 w-3 text-teal-600" /> QA Evaluation
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700 border border-slate-200 capitalize">
            {action.replace("_", " ")}
          </span>
        );
    }
  };

  const totalRequestsCount = summary?.total_requests || 0;
  const totalPages = Math.max(1, Math.ceil(totalRequestsCount / pageSize));

  return (
    <div className="page-transition max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-8 space-y-6 sm:space-y-8 overflow-x-hidden">
      {/* Header Banner & Mobile-First Filters */}
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:pb-6">
        <div className="space-y-1">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2 sm:gap-3">
            <DollarSign className="h-6 w-6 sm:h-8 sm:w-8 text-emerald-600 shrink-0" />
            <span>LLM Cost & Token Analytics</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 leading-normal max-w-full">
            Real-time token metrics, call evaluation costs, and audio transcript cost attribution
          </p>
        </div>

        {/* Filters Bar - Stacked on Mobile, Inline on Desktop */}
        <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2.5 sm:gap-3 w-full pt-1">
          {/* Date Filter Dropdown */}
          <div className="flex items-center justify-between sm:justify-start gap-2 rounded-xl bg-white px-3 py-2 border border-slate-200 shadow-xs w-full sm:w-auto">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-700 shrink-0">
              <Calendar className="h-4 w-4 text-indigo-600 shrink-0" />
              <span>Date:</span>
            </div>
            <select
              value={selectedDatePreset}
              onChange={(e) => {
                setSelectedDatePreset(e.target.value);
                setPage(1);
              }}
              className="rounded-lg bg-slate-50 border border-slate-200 px-2.5 py-1 text-xs font-bold text-slate-900 focus:border-teal-500 focus:outline-none cursor-pointer text-right sm:text-left min-w-[110px]"
            >
              <option value="all">All Time</option>
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="7days">Last 7 Days</option>
              <option value="30days">Last 30 Days</option>
            </select>
          </div>

          {/* Evaluator Filter Dropdown */}
          <div className="flex items-center justify-between sm:justify-start gap-2 rounded-xl bg-white px-3 py-2 border border-slate-200 shadow-xs w-full sm:w-auto">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-700 shrink-0">
              <UserCheck className="h-4 w-4 text-teal-600 shrink-0" />
              <span>Evaluator:</span>
            </div>
            <select
              value={selectedUserId}
              onChange={(e) => {
                setSelectedUserId(e.target.value);
                setPage(1);
              }}
              className="rounded-lg bg-slate-50 border border-slate-200 px-2.5 py-1 text-xs font-bold text-slate-900 focus:border-teal-500 focus:outline-none cursor-pointer truncate max-w-[180px] text-right sm:text-left"
            >
              <option value="">All Evaluators & System</option>
              {teamMembers.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name || member.email} ({member.role})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* KPI Overview Grid */}
      <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Spend */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
              Total USD Spend
            </span>
            <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-200">
              <DollarSign className="h-4 w-4 sm:h-5 sm:w-5" />
            </div>
          </div>
          <p className="mt-2 sm:mt-3 text-2xl sm:text-3xl font-black text-slate-900">
            {isLoadingSummary ? "..." : formatUsd(summary?.total_spend_usd)}
          </p>
          <p className="mt-1 text-[10px] sm:text-[11px] text-slate-400 font-medium">
            {selectedDatePreset !== "all" || selectedUserId ? "Filtered spend calculation" : "Calculated across all LLM & STT calls"}
          </p>
        </div>

        {/* Total Tokens */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
              Total Tokens Consumed
            </span>
            <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-200">
              <Cpu className="h-4 w-4 sm:h-5 sm:w-5" />
            </div>
          </div>
          <p className="mt-2 sm:mt-3 text-2xl sm:text-3xl font-black text-slate-900">
            {isLoadingSummary ? "..." : formatNumber(summary?.total_tokens)}
          </p>
          <div className="mt-1 flex items-center gap-2 sm:gap-3 text-[10px] text-slate-500 font-semibold">
            <span>In: {formatNumber(summary?.prompt_tokens)}</span>
            <span>•</span>
            <span>Out: {formatNumber(summary?.completion_tokens)}</span>
          </div>
        </div>

        {/* Total Requests */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
              Total API Requests
            </span>
            <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-600 border border-teal-200">
              <Zap className="h-4 w-4 sm:h-5 sm:w-5" />
            </div>
          </div>
          <p className="mt-2 sm:mt-3 text-2xl sm:text-3xl font-black text-slate-900">
            {isLoadingSummary ? "..." : formatNumber(summary?.total_requests)}
          </p>
          <p className="mt-1 text-[10px] sm:text-[11px] text-slate-400 font-medium">
            STT, Diarization & QA evaluation runs
          </p>
        </div>

        {/* Average Latency */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
              Average Latency
            </span>
            <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-600 border border-amber-200">
              <Clock className="h-4 w-4 sm:h-5 sm:w-5" />
            </div>
          </div>
          <p className="mt-2 sm:mt-3 text-2xl sm:text-3xl font-black text-slate-900">
            {isLoadingSummary ? "..." : `${formatNumber(summary?.avg_latency_ms)} ms`}
          </p>
          <p className="mt-1 text-[10px] sm:text-[11px] text-slate-400 font-medium">
            Average response execution time
          </p>
        </div>
      </div>

      {/* Model Breakdown Section */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-slate-100 pb-3">
          <h2 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-teal-600 shrink-0" /> Model Spend & Token Breakdown
          </h2>
          <span className="text-[10px] sm:text-[11px] font-semibold text-slate-500">
            Grouped by LLM / STT Model & Provider
          </span>
        </div>

        {isLoadingBreakdown ? (
          <div className="h-32 rounded-xl bg-slate-50 animate-pulse border border-slate-200" />
        ) : breakdown.length === 0 ? (
          <p className="text-xs text-slate-400 py-6 text-center italic">No model request data logged for this filter.</p>
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-left text-xs min-w-[550px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-700 font-bold uppercase text-[10px]">
                  <th className="py-2.5 px-3">Model Name</th>
                  <th className="py-2.5 px-3">Provider</th>
                  <th className="py-2.5 px-3 text-center">Requests</th>
                  <th className="py-2.5 px-3 text-right">Total Tokens</th>
                  <th className="py-2.5 px-3 text-right">Total Cost (USD)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {breakdown.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-900 flex items-center gap-2 whitespace-nowrap">
                      <Server className="h-3.5 w-3.5 text-teal-600 shrink-0" /> {row.model_name}
                    </td>
                    <td className="py-2.5 px-3 capitalize font-semibold text-slate-600 whitespace-nowrap">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 border border-slate-200">
                        {row.provider}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center font-bold">{formatNumber(row.request_count)}</td>
                    <td className="py-2.5 px-3 text-right font-mono">{formatNumber(row.total_tokens)}</td>
                    <td className="py-2.5 px-3 text-right font-mono font-black text-emerald-600 whitespace-nowrap">
                      {formatUsd(row.total_cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Live Request Audit Logs (Mobile Cards + Desktop Table) */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <h2 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-600 shrink-0" /> Live Request Audit Logs ({totalRequestsCount})
          </h2>

          {/* Model Filter */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <select
              value={selectedModel}
              onChange={(e) => {
                setSelectedModel(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-800 focus:border-teal-500 focus:outline-none cursor-pointer w-full sm:w-auto"
            >
              <option value="">All LLM / STT Models</option>
              {breakdown.map((b, idx) => (
                <option key={idx} value={b.model_name}>
                  {b.model_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {isLoadingLogs ? (
          <div className="h-48 rounded-xl bg-slate-50 animate-pulse border border-slate-200" />
        ) : logs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-6 sm:p-8 text-center bg-slate-50">
            <p className="text-xs text-slate-500 font-semibold">No request log entries recorded for this filter.</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Select a different date range or trigger AI audio transcription runs to record metrics.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* MOBILE VIEW (< md): Card-Based Layout */}
            <div className="block md:hidden space-y-3">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 space-y-2.5 shadow-2xs hover:bg-slate-100/70 transition-colors"
                >
                  {/* Top Bar: Action Badge + Status */}
                  <div className="flex items-center justify-between gap-2 border-b border-slate-200/60 pb-2">
                    <div className="flex items-center gap-1.5">
                      {renderActionBadge(log.action)}
                    </div>
                    {log.status === "success" ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[9px] font-bold text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="h-3 w-3 text-emerald-600" /> Success
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[9px] font-bold text-rose-700 border border-rose-200">
                        <XCircle className="h-3 w-3 text-rose-600" /> Failed
                      </span>
                    )}
                  </div>

                  {/* Transcript Reference */}
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400 block mb-0.5">Call Reference</span>
                    {log.transcript_id || log.analysis_run_id ? (
                      <div className="space-y-1">
                        {log.transcript_id ? (
                          <Link
                            href={`/transcripts/${log.transcript_id}`}
                            className="text-teal-700 hover:text-teal-900 font-bold flex items-center gap-1 text-xs truncate"
                          >
                            <FileText className="h-3.5 w-3.5 shrink-0 text-teal-600" />
                            <span className="truncate">{log.source_call_id || log.transcript_id.substring(0, 10)}</span>
                            <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
                          </Link>
                        ) : (
                          <span className="text-slate-500 font-medium italic text-xs">Deleted Transcript</span>
                        )}
                        {log.analysis_run_id && (
                          <Link
                            href={`/analysis-runs/${log.analysis_run_id}`}
                            className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold block truncate"
                          >
                            Run ID: {log.analysis_run_id.substring(0, 8)}...
                          </Link>
                        )}
                      </div>
                    ) : (
                      <span className="text-slate-400 italic text-xs font-medium">Deleted Call / Unlinked Log</span>
                    )}
                  </div>

                  {/* Evaluator + Model */}
                  <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-200/40">
                    <div className="flex items-center gap-1 text-slate-600 font-medium">
                      <User className="h-3 w-3 text-slate-400" />
                      <span>{log.user_name || log.user_email || "System"}</span>
                    </div>
                    <span className="rounded-full bg-slate-200/70 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-800">
                      {log.model_name}
                    </span>
                  </div>

                  {/* Metrics Footer: Tokens, Latency & Cost */}
                  <div className="flex items-center justify-between bg-white rounded-lg p-2 border border-slate-200 text-xs font-mono">
                    <div className="text-[10px] text-slate-500">
                      Tokens: <span className="text-slate-900 font-bold">{formatNumber(log.total_tokens)}</span> ({log.latency_ms}ms)
                    </div>
                    <div className="font-black text-emerald-700">
                      {formatUsd(log.total_cost_usd)}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* DESKTOP VIEW (>= md): Full Responsive Table */}
            <div className="hidden md:block overflow-x-auto scrollbar-thin">
              <table className="w-full text-left text-xs min-w-[850px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-700 font-bold uppercase text-[10px]">
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Transcript & Call Reference</th>
                    <th className="py-3 px-4">Evaluator / User</th>
                    <th className="py-3 px-4">Model</th>
                    <th className="py-3 px-4 text-center">Prompt / Compl. Tokens</th>
                    <th className="py-3 px-4 text-center">Latency</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-right">Cost (USD)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4 text-[11px] text-slate-500 font-mono whitespace-nowrap">
                        {formatToUserLocalTime(log.created_at)}
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                        {renderActionBadge(log.action)}
                      </td>

                      {/* Audio Transcript & Call Reference */}
                      <td className="py-3 px-4 max-w-[220px]">
                        {log.transcript_id || log.analysis_run_id ? (
                          <div className="space-y-1">
                            {log.transcript_id ? (
                              <Link
                                href={`/transcripts/${log.transcript_id}`}
                                className="text-teal-700 hover:text-teal-900 font-bold flex items-center gap-1.5 group truncate"
                                title={log.source_call_id || log.transcript_id}
                              >
                                <FileText className="h-3.5 w-3.5 shrink-0 text-teal-600 group-hover:scale-110 transition-transform" />
                                <span className="truncate">{log.source_call_id || log.transcript_id.substring(0, 8)}</span>
                                <ExternalLink className="h-3 w-3 shrink-0 opacity-50 group-hover:opacity-100" />
                              </Link>
                            ) : (
                              <span className="text-slate-500 font-medium italic text-[11px]">Deleted Transcript</span>
                            )}

                            {log.analysis_run_id && (
                              <Link
                                href={`/analysis-runs/${log.analysis_run_id}`}
                                className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold block truncate"
                              >
                                Run ID: {log.analysis_run_id.substring(0, 8)}...
                              </Link>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400 italic text-[11px] font-medium">Deleted Call / Unlinked Log</span>
                        )}
                      </td>

                      {/* Evaluator / User */}
                      <td className="py-3 px-4 text-slate-700 font-semibold truncate max-w-[130px]">
                        {log.user_name || log.user_email || "System"}
                      </td>

                      {/* Model Name */}
                      <td className="py-3 px-4 font-mono text-[11px]">
                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 border border-slate-200 text-slate-700 font-bold whitespace-nowrap">
                          {log.model_name}
                        </span>
                      </td>

                      {/* Tokens */}
                      <td className="py-3 px-4 text-center font-mono text-[11px] whitespace-nowrap">
                        <span className="text-slate-500">{formatNumber(log.prompt_tokens)}</span> /{" "}
                        <span className="text-slate-900 font-bold">{formatNumber(log.completion_tokens)}</span>
                      </td>

                      {/* Latency */}
                      <td className="py-3 px-4 text-center font-mono text-[11px] text-slate-600 whitespace-nowrap">
                        {log.latency_ms} ms
                      </td>

                      {/* Status Badge */}
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        {log.status === "success" ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" /> Success
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200" title={log.error_message || "Failed"}>
                            <XCircle className="h-3 w-3 text-rose-600" /> Failed
                          </span>
                        )}
                      </td>

                      {/* Cost */}
                      <td className="py-3 px-4 text-right font-mono font-bold text-emerald-700 whitespace-nowrap">
                        {formatUsd(log.total_cost_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Footer */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2 text-xs text-slate-600 w-full sm:w-auto justify-between sm:justify-start">
                <span className="text-[11px]">Items:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-bold text-slate-800 focus:outline-none cursor-pointer"
                >
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
                <span className="font-semibold text-slate-500 text-[11px] truncate">
                  {Math.min((page - 1) * pageSize + 1, totalRequestsCount)}-
                  {Math.min(page * pageSize, totalRequestsCount)} of {totalRequestsCount}
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
