"use client";

import React, { useState } from "react";
import {
  Award,
  CheckCircle2,
  Quote,
  Lightbulb,
  Layers,
  FileText,
  Sparkles,
  UserCheck,
  User,
  TrendingUp,
  XCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Printer,
  MessageSquare,
  AlignLeft,
  Phone,
  Calendar,
  Cpu,
  ShieldCheck,
  BarChart3,
} from "lucide-react";

export interface ParameterResult {
  id: string;
  parameter_id?: string;
  name_snapshot: string;
  ai_instructions_snapshot: string;
  score: number;
  max_score: number;
  reason: string;
  evidence?: string;
  suggestion?: string;
  confidence?: number;
}

export interface SectionResult {
  id: string;
  section_id?: string;
  name_snapshot: string;
  extracted_content: string;
}

interface DynamicResultsListProps {
  overallScore: number | null;
  parameterResults: ParameterResult[];
  sectionResults: SectionResult[];
  llmModelUsed?: string;
  templateName?: string;
  templateVersion?: number;
  callReference?: string;
  evaluatedAt?: string;
  creator?: {
    full_name?: string;
    email: string;
    role?: string;
  };
  tokenUsage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  transcript?: {
    raw_text?: string;
    speaker_segments?: { diarized_text?: string };
  };
}

function getGradeInfo(score: number | null): {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  ringColor: string;
} {
  if (score === null) return { label: "N/A", color: "text-slate-500", bgColor: "bg-slate-50", borderColor: "border-slate-200", ringColor: "ring-slate-300" };
  if (score >= 90) return { label: "Excellent", color: "text-emerald-700", bgColor: "bg-emerald-50", borderColor: "border-emerald-300", ringColor: "ring-emerald-400" };
  if (score >= 75) return { label: "Good", color: "text-teal-700", bgColor: "bg-teal-50", borderColor: "border-teal-300", ringColor: "ring-teal-400" };
  if (score >= 60) return { label: "Average", color: "text-amber-700", bgColor: "bg-amber-50", borderColor: "border-amber-300", ringColor: "ring-amber-400" };
  if (score >= 40) return { label: "Needs Improvement", color: "text-orange-700", bgColor: "bg-orange-50", borderColor: "border-orange-300", ringColor: "ring-orange-400" };
  return { label: "Poor", color: "text-rose-700", bgColor: "bg-rose-50", borderColor: "border-rose-300", ringColor: "ring-rose-400" };
}

function getParamBadge(score: number, maxScore: number) {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  if (pct >= 80) return { text: "Pass", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  if (pct >= 60) return { text: "Average", cls: "bg-amber-50 text-amber-700 border-amber-200" };
  return { text: "Fail", cls: "bg-rose-50 text-rose-700 border-rose-200" };
}

function getParamBarColor(score: number, maxScore: number) {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  if (pct >= 80) return "bg-emerald-500";
  if (pct >= 60) return "bg-amber-400";
  return "bg-rose-500";
}

function ScoreGauge({ score }: { score: number | null }) {
  const grade = getGradeInfo(score);
  const displayScore = score !== null ? score.toFixed(1) : "—";
  const circumference = 2 * Math.PI * 52;
  const progress = score !== null ? (score / 100) * circumference : 0;

  const strokeColor =
    score === null ? "#cbd5e1"
    : score >= 90 ? "#10b981"
    : score >= 75 ? "#14b8a6"
    : score >= 60 ? "#f59e0b"
    : score >= 40 ? "#f97316"
    : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative flex items-center justify-center">
        <svg width="128" height="128" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="52" fill="none" stroke="#e2e8f0" strokeWidth="10" />
          <circle
            cx="64" cy="64" r="52"
            fill="none"
            stroke={strokeColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            transform="rotate(-90 64 64)"
            style={{ transition: "stroke-dasharray 0.8s ease" }}
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-2xl font-black text-slate-900 leading-none">{displayScore}</span>
          {score !== null && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">/ 100%</span>}
        </div>
      </div>
      <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${grade.bgColor} ${grade.color} ${grade.borderColor}`}>
        <Award className="h-3.5 w-3.5" />
        {grade.label}
      </span>
    </div>
  );
}

function SpeakerDialogue({ text, defaultExpanded = false }: { text: string; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const rawLines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const turns: { speaker: "Agent" | "Customer"; text: string }[] = [];
  let currentSpeaker: "Agent" | "Customer" | null = null;
  let currentText = "";

  for (let line of rawLines) {
    line = line.replace(/^(\*\*)(Agent|Customer Care|Customer|User)(\*\*):\s*/i, "$2: ");
    const isAgent = /^(Agent|Customer Care):\s*/i.test(line);
    const isCustomer = /^(Customer|User):\s*/i.test(line);
    if (isAgent || isCustomer) {
      if (currentSpeaker && currentText.trim()) turns.push({ speaker: currentSpeaker, text: currentText.trim() });
      currentSpeaker = isAgent ? "Agent" : "Customer";
      currentText = line.replace(/^(Agent|Customer Care|Customer|User):\s*/i, "");
    } else if (currentSpeaker) {
      currentText += " " + line;
    } else {
      currentSpeaker = "Customer";
      currentText = line;
    }
  }
  if (currentSpeaker && currentText.trim()) turns.push({ speaker: currentSpeaker, text: currentText.trim() });

  const displayTurns = expanded ? turns : turns.slice(0, 4);

  return (
    <div className="space-y-3">
      {displayTurns.map((turn, idx) => {
        const isAgent = turn.speaker === "Agent";
        return (
          <div
            key={idx}
            className={`rounded-xl p-3.5 border text-xs leading-relaxed ${
              isAgent
                ? "bg-indigo-50/80 border-indigo-200 text-indigo-950 sm:mr-8"
                : "bg-teal-50/80 border-teal-200 text-teal-950 sm:ml-8"
            }`}
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              {isAgent ? (
                <UserCheck className="h-3.5 w-3.5 text-indigo-600" />
              ) : (
                <User className="h-3.5 w-3.5 text-teal-600" />
              )}
              <span className={`font-bold text-[10px] uppercase tracking-wider ${isAgent ? "text-indigo-700" : "text-teal-700"}`}>
                {isAgent ? "Agent / Support Rep" : "Customer / Caller"}
              </span>
            </div>
            <p className="font-medium text-slate-800">{turn.text}</p>
          </div>
        );
      })}
      {turns.length > 4 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-center gap-1.5 w-full rounded-xl bg-slate-100 border border-slate-200 py-2 text-xs font-bold text-slate-700 hover:bg-slate-200 transition-all print:hidden"
        >
          {expanded ? (
            <><ChevronUp className="h-3.5 w-3.5" /> Collapse Dialogue</>
          ) : (
            <><ChevronDown className="h-3.5 w-3.5" /> Show Full Dialogue ({turns.length} turns)</>
          )}
        </button>
      )}
    </div>
  );
}

export function DynamicResultsList({
  overallScore,
  parameterResults = [],
  sectionResults = [],
  llmModelUsed,
  templateName,
  templateVersion,
  callReference,
  evaluatedAt,
  creator,
  tokenUsage,
  transcript,
}: DynamicResultsListProps) {
  const [transcriptViewMode, setTranscriptViewMode] = useState<"dialogue" | "raw">("dialogue");
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);

  const grade = getGradeInfo(overallScore);
  const passCount = parameterResults.filter((p) => p.max_score > 0 && (p.score / p.max_score) >= 0.8).length;
  const failCount = parameterResults.filter((p) => p.max_score > 0 && (p.score / p.max_score) < 0.6).length;
  const avgCount = parameterResults.length - passCount - failCount;

  const dialogueText = transcript?.speaker_segments?.diarized_text || transcript?.raw_text || "";

  const reportDate = evaluatedAt
    ? new Date(evaluatedAt).toLocaleString()
    : new Date().toLocaleString();

  return (
    <div className="space-y-6 report-content">

      {/* ── REPORT HEADER ─────────────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm print:shadow-none print:border-slate-300">
        {/* Top accent bar */}
        <div className="h-1.5 bg-gradient-to-r from-teal-500 via-indigo-500 to-purple-500" />

        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">

            {/* Left: Report Title & Metadata */}
            <div className="flex-1 space-y-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-bold text-teal-700">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Call Quality Assurance Report
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-bold text-emerald-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  AI Evaluated
                </span>
              </div>

              <div>
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900">
                  Agent Performance Scorecard
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                  Automated quality evaluation against defined scorecard criteria
                </p>
              </div>

              {/* Metadata grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                {callReference && (
                  <div className="flex items-center gap-2 text-xs">
                    <Phone className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="text-slate-500 font-medium">Call Reference:</span>
                    <span className="font-bold text-slate-900 font-mono">{callReference}</span>
                  </div>
                )}
                <div className="flex items-center gap-2 text-xs">
                  <Calendar className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                  <span className="text-slate-500 font-medium">Evaluated:</span>
                  <span className="font-bold text-slate-900">{reportDate}</span>
                </div>
                {creator && (
                  <div className="flex items-center gap-2 text-xs">
                    <UserCheck className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                    <span className="text-slate-500 font-medium">Evaluator:</span>
                    <span className="font-bold text-slate-900">
                      {creator.full_name || creator.email.split("@")[0]}
                    </span>
                  </div>
                )}
                {templateName && (
                  <div className="flex items-center gap-2 text-xs">
                    <FileText className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="text-slate-500 font-medium">Scorecard:</span>
                    <span className="font-bold text-slate-900">
                      {templateName}{templateVersion ? ` (v${templateVersion})` : ""}
                    </span>
                  </div>
                )}
                {llmModelUsed && (
                  <div className="flex items-center gap-2 text-xs">
                    <Cpu className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="text-slate-500 font-medium">AI Model:</span>
                    <span className="font-mono font-bold text-slate-900">{llmModelUsed}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Score Gauge */}
            <div className="flex flex-col items-center gap-4 lg:items-end">
              <ScoreGauge score={overallScore} />
              <div className="flex items-center gap-3 text-xs font-bold">
                <span className="flex items-center gap-1 text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" /> {passCount} Pass
                </span>
                <span className="flex items-center gap-1 text-amber-600">
                  <AlertCircle className="h-3.5 w-3.5" /> {avgCount} Avg
                </span>
                <span className="flex items-center gap-1 text-rose-600">
                  <XCircle className="h-3.5 w-3.5" /> {failCount} Fail
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── SCORE DISTRIBUTION BAR ────────────────────────────────── */}
      {parameterResults.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm print:shadow-none">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-indigo-600" />
            Parameter Score Overview
          </h2>
          <div className="space-y-2.5">
            {parameterResults.map((p) => {
              const pct = p.max_score > 0 ? Math.round((p.score / p.max_score) * 100) : 0;
              const barColor = getParamBarColor(p.score, p.max_score);
              const badge = getParamBadge(p.score, p.max_score);
              return (
                <div key={p.id} className="flex items-center gap-3">
                  <span className="w-40 sm:w-56 text-xs font-semibold text-slate-700 truncate shrink-0" title={p.name_snapshot}>
                    {p.name_snapshot}
                  </span>
                  <div className="flex-1 relative h-4 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`absolute inset-y-0 left-0 rounded-full ${barColor} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-16 text-right text-xs font-bold text-slate-700 shrink-0">
                    {p.score}/{p.max_score}
                  </span>
                  <span className={`hidden sm:inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-bold shrink-0 ${badge.cls}`}>
                    {badge.text}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── PARAMETER EVALUATIONS ─────────────────────────────────── */}
      <div className="space-y-3">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-teal-600" />
          Detailed Parameter Evaluations
          <span className="text-sm font-semibold text-slate-400">({parameterResults.length})</span>
        </h2>

        <div className="space-y-4">
          {parameterResults.map((result, idx) => {
            const pct = result.max_score > 0 ? Math.round((result.score / result.max_score) * 100) : 0;
            const barColor = getParamBarColor(result.score, result.max_score);
            const badge = getParamBadge(result.score, result.max_score);

            return (
              <div
                key={result.id}
                className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs print:shadow-none print:break-inside-avoid"
              >
                {/* Parameter header row */}
                <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-slate-100 bg-slate-50/60">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-700">
                      {idx + 1}
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-slate-900 truncate">{result.name_snapshot}</h3>
                      <p className="text-[10px] text-slate-500 truncate mt-0.5">{result.ai_instructions_snapshot}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`rounded-lg border px-2 py-0.5 text-xs font-bold ${badge.cls}`}>
                      {badge.text}
                    </span>
                    <span className="text-base font-black text-slate-900">
                      {result.score}<span className="text-slate-400 font-semibold text-sm">/{result.max_score}</span>
                    </span>
                  </div>
                </div>

                {/* Score bar */}
                <div className="h-1.5 bg-slate-100">
                  <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
                </div>

                {/* Parameter body */}
                <div className="px-5 py-4 space-y-3">
                  {/* Reason */}
                  <div className="flex items-start gap-2">
                    <TrendingUp className="h-3.5 w-3.5 text-slate-400 shrink-0 mt-0.5" />
                    <p className="text-xs leading-relaxed text-slate-800 font-medium">{result.reason}</p>
                  </div>

                  {/* Evidence */}
                  {result.evidence && (
                    <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-3.5">
                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-700 uppercase tracking-wider mb-1.5">
                        <Quote className="h-3 w-3" /> Evidence from Transcript
                      </div>
                      <p className="text-xs italic text-indigo-900 leading-relaxed font-medium">
                        "{result.evidence}"
                      </p>
                    </div>
                  )}

                  {/* Suggestion */}
                  {result.suggestion && (
                    <div className="flex items-start gap-2.5 rounded-xl bg-teal-50 border border-teal-200 p-3.5">
                      <Lightbulb className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-[10px] font-bold text-teal-700 uppercase tracking-wider mb-0.5">Improvement Tip</p>
                        <p className="text-xs text-teal-950 leading-relaxed font-medium">{result.suggestion}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── EXTRACTION SECTIONS ───────────────────────────────────── */}
      {sectionResults.length > 0 && (
        <div className="space-y-3 pt-2">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-600" />
            Extracted Call Information
            <span className="text-sm font-semibold text-slate-400">({sectionResults.length})</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {sectionResults.map((sec) => (
              <div
                key={sec.id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs print:shadow-none print:break-inside-avoid"
              >
                <h3 className="text-xs font-bold text-indigo-700 flex items-center gap-2 mb-3 uppercase tracking-wider">
                  <FileText className="h-3.5 w-3.5" />
                  {sec.name_snapshot}
                </h3>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-800 bg-slate-50 p-3.5 rounded-xl border border-slate-200 font-medium">
                  {sec.extracted_content || "No information extracted."}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── FULL CALL TRANSCRIPT ──────────────────────────────────── */}
      {transcript && (dialogueText || transcript.raw_text) && (
        <div className="rounded-2xl border border-slate-200 bg-white shadow-xs print:shadow-none print:break-inside-avoid">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <FileText className="h-4 w-4 text-teal-600" />
              Full Call Transcript
            </h2>
            <div className="flex items-center gap-2">
              {/* View mode toggle */}
              <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs print:hidden">
                <button
                  onClick={() => setTranscriptViewMode("dialogue")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                    transcriptViewMode === "dialogue" ? "bg-teal-600 text-white" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <MessageSquare className="h-3 w-3" /> Dialogue
                </button>
                <button
                  onClick={() => setTranscriptViewMode("raw")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${
                    transcriptViewMode === "raw" ? "bg-teal-600 text-white" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <AlignLeft className="h-3 w-3" /> Raw Text
                </button>
              </div>

              <button
                onClick={() => setTranscriptExpanded(!transcriptExpanded)}
                className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 print:hidden"
              >
                {transcriptExpanded ? <><ChevronUp className="h-3.5 w-3.5" /> Collapse</> : <><ChevronDown className="h-3.5 w-3.5" /> Expand</>}
              </button>
            </div>
          </div>

          <div className={`px-5 py-4 ${!transcriptExpanded ? "max-h-64 overflow-hidden relative" : ""}`}>
            {!transcriptExpanded && (
              <div className="absolute bottom-0 inset-x-0 h-20 bg-gradient-to-t from-white to-transparent z-10 print:hidden" />
            )}

            {transcriptViewMode === "dialogue" && dialogueText ? (
              <SpeakerDialogue text={dialogueText} defaultExpanded={transcriptExpanded} />
            ) : (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800 whitespace-pre-wrap">
                {transcript.raw_text || dialogueText}
              </div>
            )}
          </div>

          {!transcriptExpanded && (
            <div className="px-5 pb-4 print:hidden">
              <button
                onClick={() => setTranscriptExpanded(true)}
                className="flex items-center justify-center gap-1.5 w-full rounded-xl bg-slate-50 border border-slate-200 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 transition-all"
              >
                <ChevronDown className="h-4 w-4" /> Show Full Transcript
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── REPORT FOOTER ─────────────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-5 py-4 flex flex-wrap items-center justify-between gap-4 text-[10px] text-slate-400 font-medium print:mt-8 print:border-t print:border-slate-200 print:rounded-none print:bg-transparent">
        <div className="flex items-center gap-4">
          {tokenUsage?.total_tokens && (
            <span className="flex items-center gap-1">
              <Cpu className="h-3 w-3" /> {tokenUsage.total_tokens.toLocaleString()} tokens used
            </span>
          )}
          {llmModelUsed && (
            <span className="font-mono">{llmModelUsed}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Sparkles className="h-3 w-3" />
          Generated by AI Call Quality System · {reportDate}
        </div>
      </div>
    </div>
  );
}
