"use client";

import React, { useState, useRef, useCallback } from "react";
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
  MessageSquare,
  AlignLeft,
  Phone,
  Calendar,
  Cpu,
  ShieldCheck,
  BarChart3,
  Search,
  X,
  SlidersHorizontal,
  Hash,
  Globe,
  Info,
  Copy,
  Check,
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
    detected_language?: string | null;
    audio_duration_seconds?: number | null;
  };
}

type FilterTab = "all" | "pass" | "average" | "fail";

function getGradeInfo(score: number | null) {
  if (score === null) return { label: "N/A", color: "text-slate-500", bgColor: "bg-slate-50", borderColor: "border-slate-200" };
  if (score >= 90) return { label: "Excellent", color: "text-emerald-700", bgColor: "bg-emerald-50", borderColor: "border-emerald-300" };
  if (score >= 75) return { label: "Good", color: "text-teal-700", bgColor: "bg-teal-50", borderColor: "border-teal-300" };
  if (score >= 60) return { label: "Average", color: "text-amber-700", bgColor: "bg-amber-50", borderColor: "border-amber-300" };
  if (score >= 40) return { label: "Needs Improvement", color: "text-orange-700", bgColor: "bg-orange-50", borderColor: "border-orange-300" };
  return { label: "Poor", color: "text-rose-700", bgColor: "bg-rose-50", borderColor: "border-rose-300" };
}

function getParamStatus(score: number, maxScore: number): "pass" | "average" | "fail" {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  if (pct >= 80) return "pass";
  if (pct >= 60) return "average";
  return "fail";
}

function getParamBadge(status: "pass" | "average" | "fail") {
  if (status === "pass") return { text: "Pass", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  if (status === "average") return { text: "Average", cls: "bg-amber-50 text-amber-700 border-amber-200" };
  return { text: "Fail", cls: "bg-rose-50 text-rose-700 border-rose-200" };
}

function getParamBarColor(status: "pass" | "average" | "fail") {
  if (status === "pass") return "bg-emerald-500";
  if (status === "average") return "bg-amber-400";
  return "bg-rose-500";
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="bg-yellow-200 text-yellow-900 rounded px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function ScoreGauge({ score }: { score: number | null }) {
  const grade = getGradeInfo(score);
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
          <circle cx="64" cy="64" r="52" fill="none" stroke={strokeColor} strokeWidth="10"
            strokeLinecap="round" strokeDasharray={`${progress} ${circumference}`}
            transform="rotate(-90 64 64)" style={{ transition: "stroke-dasharray 0.8s ease" }} />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-2xl font-black text-slate-900 leading-none">
            {score !== null ? score.toFixed(1) : "—"}
          </span>
          {score !== null && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">/ 100%</span>}
        </div>
      </div>
      <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${grade.bgColor} ${grade.color} ${grade.borderColor}`}>
        <Award className="h-3.5 w-3.5" />{grade.label}
      </span>
    </div>
  );
}

function SpeakerDialogue({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
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
    } else { currentSpeaker = "Customer"; currentText = line; }
  }
  if (currentSpeaker && currentText.trim()) turns.push({ speaker: currentSpeaker, text: currentText.trim() });

  const screenTurns = expanded ? turns : turns.slice(0, 4);
  const hiddenTurns = turns.slice(4);

  return (
    <div className="space-y-3">
      {screenTurns.map((turn, idx) => {
        const isAgent = turn.speaker === "Agent";
        return (
          <div key={idx} className={`rounded-xl p-3.5 border text-xs leading-relaxed ${isAgent ? "bg-indigo-50/80 border-indigo-200 sm:mr-8" : "bg-teal-50/80 border-teal-200 sm:ml-8"}`}>
            <div className="flex items-center gap-1.5 mb-1.5">
              {isAgent ? <UserCheck className="h-3.5 w-3.5 text-indigo-600" /> : <User className="h-3.5 w-3.5 text-teal-600" />}
              <span className={`font-bold text-[10px] uppercase tracking-wider ${isAgent ? "text-indigo-700" : "text-teal-700"}`}>
                {isAgent ? "Agent / Support Rep" : "Customer / Caller"}
              </span>
            </div>
            <p className="font-medium text-slate-800">{turn.text}</p>
          </div>
        );
      })}

      {/* When not expanded on screen, render the remaining turns in hidden print:block so PDF prints 100% of dialogue */}
      {!expanded && hiddenTurns.length > 0 && (
        <div className="hidden print:block space-y-3">
          {hiddenTurns.map((turn, idx) => {
            const isAgent = turn.speaker === "Agent";
            return (
              <div key={idx + 4} className={`rounded-xl p-3.5 border text-xs leading-relaxed ${isAgent ? "bg-indigo-50/80 border-indigo-200 sm:mr-8" : "bg-teal-50/80 border-teal-200 sm:ml-8"}`}>
                <div className="flex items-center gap-1.5 mb-1.5">
                  {isAgent ? <UserCheck className="h-3.5 w-3.5 text-indigo-600" /> : <User className="h-3.5 w-3.5 text-teal-600" />}
                  <span className={`font-bold text-[10px] uppercase tracking-wider ${isAgent ? "text-indigo-700" : "text-teal-700"}`}>
                    {isAgent ? "Agent / Support Rep" : "Customer / Caller"}
                  </span>
                </div>
                <p className="font-medium text-slate-800">{turn.text}</p>
              </div>
            );
          })}
        </div>
      )}

      {turns.length > 4 && (
        <button onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-center gap-1.5 w-full rounded-xl bg-slate-100 border border-slate-200 py-2 text-xs font-bold text-slate-700 hover:bg-slate-200 transition-all print:hidden">
          {expanded ? <><ChevronUp className="h-3.5 w-3.5" /> Collapse</> : <><ChevronDown className="h-3.5 w-3.5" /> Show All ({turns.length} turns)</>}
        </button>
      )}
    </div>
  );
}

export function DynamicResultsList({
  overallScore, parameterResults = [], sectionResults = [],
  llmModelUsed, templateName, templateVersion, callReference, evaluatedAt,
  creator, tokenUsage, transcript,
}: DynamicResultsListProps) {
  // ── Filter & Search State ──────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [filterTab, setFilterTab] = useState<FilterTab>("all");
  const [collapsedParams, setCollapsedParams] = useState<Set<string>>(new Set());
  const [transcriptViewMode, setTranscriptViewMode] = useState<"dialogue" | "raw">("dialogue");
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);
  const [copiedTranscript, setCopiedTranscript] = useState(false);

  const handleCopyTranscript = () => {
    const textToCopy = transcript?.speaker_segments?.diarized_text || transcript?.raw_text || "";
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopiedTranscript(true);
    setTimeout(() => setCopiedTranscript(false), 2000);
  };

  // ── Section refs for jump nav ─────────────────────────────────
  const overviewRef = useRef<HTMLDivElement>(null);
  const parametersRef = useRef<HTMLDivElement>(null);
  const sectionsRef = useRef<HTMLDivElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const scrollTo = useCallback((ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // Scroll to a specific parameter card by id
  const scrollToParam = useCallback((paramId: string) => {
    const el = document.getElementById(`param-${paramId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const grade = getGradeInfo(overallScore);
  const passCount = parameterResults.filter((p) => getParamStatus(p.score, p.max_score) === "pass").length;
  const avgCount = parameterResults.filter((p) => getParamStatus(p.score, p.max_score) === "average").length;
  const failCount = parameterResults.filter((p) => getParamStatus(p.score, p.max_score) === "fail").length;

  const dialogueText = transcript?.speaker_segments?.diarized_text || transcript?.raw_text || "";
  const reportDate = evaluatedAt ? new Date(evaluatedAt).toLocaleString() : new Date().toLocaleString();

  // ── Filter + Search logic ─────────────────────────────────────
  const filteredParameters = parameterResults.filter((p) => {
    const status = getParamStatus(p.score, p.max_score);
    if (filterTab !== "all" && status !== filterTab) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.name_snapshot.toLowerCase().includes(q) ||
      p.reason.toLowerCase().includes(q) ||
      (p.evidence || "").toLowerCase().includes(q) ||
      (p.suggestion || "").toLowerCase().includes(q) ||
      p.ai_instructions_snapshot.toLowerCase().includes(q)
    );
  });

  const filteredSections = sectionResults.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return s.name_snapshot.toLowerCase().includes(q) || s.extracted_content.toLowerCase().includes(q);
  });

  const toggleCollapse = (id: string) => {
    setCollapsedParams((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const collapseAll = () => setCollapsedParams(new Set(parameterResults.map((p) => p.id)));
  const expandAll = () => setCollapsedParams(new Set());

  return (
    <div className="space-y-5 report-content">

      {/* ── REPORT HEADER ─────────────────────────────────────────── */}
      <div ref={overviewRef} className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm print:shadow-none">
        <div className="h-1.5 bg-gradient-to-r from-teal-500 via-indigo-500 to-purple-500" />
        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1 space-y-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-bold text-teal-700">
                  <ShieldCheck className="h-3.5 w-3.5" /> Call Quality Assurance Report
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-bold text-emerald-700">
                  <Sparkles className="h-3.5 w-3.5" /> AI Evaluated
                </span>
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900">Agent Performance Scorecard</h1>
                <p className="mt-1 text-sm text-slate-500">Automated quality evaluation against defined scorecard criteria</p>
              </div>
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
                {transcript?.detected_language && (
                  <div className="flex items-center gap-2 text-xs flex-wrap">
                    <Globe className="h-3.5 w-3.5 text-teal-600 shrink-0" />
                    <span className="text-slate-500 font-medium">Spoken Languages:</span>
                    <div className="flex items-center gap-1 flex-wrap">
                      {transcript.detected_language
                        .split(",")
                        .map((l) => l.trim())
                        .filter(Boolean)
                        .map((lang, idx) => (
                          <span
                            key={idx}
                            className="font-bold text-teal-800 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded-md text-[11px] capitalize"
                          >
                            {lang}
                          </span>
                        ))}
                    </div>
                  </div>
                )}
                {creator && (
                  <div className="flex items-center gap-2 text-xs">
                    <UserCheck className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                    <span className="text-slate-500 font-medium">Evaluator:</span>
                    <span className="font-bold text-slate-900">{creator.full_name || creator.email.split("@")[0]}</span>
                  </div>
                )}
                {templateName && (
                  <div className="flex items-center gap-2 text-xs">
                    <FileText className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="text-slate-500 font-medium">Scorecard:</span>
                    <span className="font-bold text-slate-900">{templateName}{templateVersion ? ` (v${templateVersion})` : ""}</span>
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
            <div className="flex flex-col items-center gap-4">
              <ScoreGauge score={overallScore} />
              <div className="flex items-center gap-3 text-xs font-bold">
                <button onClick={() => { setFilterTab("pass"); scrollTo(parametersRef); }}
                  className="flex items-center gap-1 text-emerald-700 hover:underline cursor-pointer">
                  <CheckCircle2 className="h-3.5 w-3.5" /> {passCount} Pass
                </button>
                <button onClick={() => { setFilterTab("average"); scrollTo(parametersRef); }}
                  className="flex items-center gap-1 text-amber-600 hover:underline cursor-pointer">
                  <AlertCircle className="h-3.5 w-3.5" /> {avgCount} Avg
                </button>
                <button onClick={() => { setFilterTab("fail"); scrollTo(parametersRef); }}
                  className="flex items-center gap-1 text-rose-600 hover:underline cursor-pointer">
                  <XCircle className="h-3.5 w-3.5" /> {failCount} Fail
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── STICKY SEARCH + FILTER + JUMP NAV ────────────────────── */}
      <div className="sticky top-0 z-20 rounded-2xl border border-slate-200 bg-white/95 backdrop-blur-sm shadow-md p-3 sm:p-4 space-y-3 print:hidden">

        {/* Jump-to nav */}
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1">
            <Hash className="h-3 w-3" /> Jump to:
          </span>
          <button onClick={() => scrollTo(overviewRef)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:border-teal-400 hover:text-teal-700 hover:bg-teal-50 transition-all">
            Overview
          </button>
          <button onClick={() => scrollTo(parametersRef)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:border-teal-400 hover:text-teal-700 hover:bg-teal-50 transition-all">
            Parameters ({parameterResults.length})
          </button>
          {sectionResults.length > 0 && (
            <button onClick={() => scrollTo(sectionsRef)}
              className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:border-indigo-400 hover:text-indigo-700 hover:bg-indigo-50 transition-all">
              Extracted Info ({sectionResults.length})
            </button>
          )}
          {transcript && (dialogueText || transcript.raw_text) && (
            <button onClick={() => { setTranscriptExpanded(true); scrollTo(transcriptRef); }}
              className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:border-indigo-400 hover:text-indigo-700 hover:bg-indigo-50 transition-all">
              Transcript
            </button>
          )}
        </div>

        {/* Search + Filter row */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search parameters, evidence, suggestions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-9 py-2 text-xs font-medium text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none focus:bg-white transition-all"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs shrink-0">
            <SlidersHorizontal className="h-3.5 w-3.5 text-slate-400 ml-1" />
            {(["all", "pass", "average", "fail"] as FilterTab[]).map((tab) => {
              const count = tab === "all" ? parameterResults.length
                : tab === "pass" ? passCount
                : tab === "average" ? avgCount
                : failCount;
              const active = filterTab === tab;
              const tabColor = active
                ? tab === "pass" ? "bg-emerald-600 text-white"
                : tab === "average" ? "bg-amber-500 text-white"
                : tab === "fail" ? "bg-rose-600 text-white"
                : "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900";
              return (
                <button key={tab} onClick={() => setFilterTab(tab)}
                  className={`rounded-lg px-2.5 py-1 font-bold capitalize transition-all ${tabColor}`}>
                  {tab === "all" ? "All" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  <span className="ml-1 opacity-70">({count})</span>
                </button>
              );
            })}
          </div>

          {/* Collapse/Expand all */}
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={expandAll}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-700 hover:bg-slate-50 transition-all">
              Expand All
            </button>
            <button onClick={collapseAll}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-700 hover:bg-slate-50 transition-all">
              Collapse All
            </button>
          </div>
        </div>

        {/* Active filter/search indicator */}
        {(searchQuery || filterTab !== "all") && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-slate-500 font-medium">
              Showing {filteredParameters.length} of {parameterResults.length} parameters
              {filteredSections.length < sectionResults.length ? `, ${filteredSections.length} of ${sectionResults.length} sections` : ""}
            </span>
            <button onClick={() => { setSearchQuery(""); setFilterTab("all"); }}
              className="flex items-center gap-1 text-[11px] font-bold text-teal-600 hover:underline">
              <X className="h-3 w-3" /> Clear filters
            </button>
          </div>
        )}
      </div>

      {/* ── SCORE DISTRIBUTION BAR ────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm print:shadow-none">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-4">
          <BarChart3 className="h-4 w-4 text-indigo-600" /> Parameter Score Overview
        </h2>
        <div className="space-y-2.5">
          {parameterResults.map((p) => {
            const pct = p.max_score > 0 ? Math.round((p.score / p.max_score) * 100) : 0;
            const status = getParamStatus(p.score, p.max_score);
            const barColor = getParamBarColor(status);
            const badge = getParamBadge(status);
            const isFiltered = !filteredParameters.find((fp) => fp.id === p.id);
            return (
              <div key={p.id} className={`flex items-center gap-3 transition-opacity ${isFiltered ? "opacity-30" : ""}`}>
                <button
                  onClick={() => {
                    if (isFiltered) { setFilterTab("all"); setSearchQuery(""); }
                    setTimeout(() => scrollToParam(p.id), isFiltered ? 50 : 0);
                  }}
                  className="w-40 sm:w-56 text-xs font-semibold text-slate-700 truncate shrink-0 text-left hover:text-teal-700 transition-colors underline-offset-2 hover:underline"
                  title={`Jump to: ${p.name_snapshot}`}>
                  {p.name_snapshot}
                </button>
                <div className="flex-1 relative h-4 rounded-full bg-slate-100 overflow-hidden">
                  <div className={`absolute inset-y-0 left-0 rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
                </div>
                <span className="w-14 text-right text-xs font-bold text-slate-700 shrink-0">{p.score}/{p.max_score}</span>
                <span className={`hidden sm:inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-bold shrink-0 ${badge.cls}`}>{badge.text}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── PARAMETER EVALUATIONS ─────────────────────────────────── */}
      <div ref={parametersRef} className="space-y-3 scroll-mt-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-teal-600" />
            Detailed Parameter Evaluations
            <span className="text-sm font-semibold text-slate-400">
              ({filteredParameters.length}{filteredParameters.length !== parameterResults.length ? ` of ${parameterResults.length}` : ""})
            </span>
          </h2>
        </div>

        {filteredParameters.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center">
            <Search className="mx-auto h-8 w-8 text-slate-300 mb-3" />
            <p className="text-sm font-bold text-slate-500">No parameters match your filter</p>
            <button onClick={() => { setSearchQuery(""); setFilterTab("all"); }}
              className="mt-3 text-xs font-bold text-teal-600 hover:underline">Clear filters</button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredParameters.map((result, idx) => {
              const pct = result.max_score > 0 ? Math.round((result.score / result.max_score) * 100) : 0;
              const status = getParamStatus(result.score, result.max_score);
              const barColor = getParamBarColor(status);
              const badge = getParamBadge(status);
              const isCollapsed = collapsedParams.has(result.id);
              const globalIdx = parameterResults.findIndex((p) => p.id === result.id) + 1;

              return (
                <div
                  key={result.id}
                  id={`param-${result.id}`}
                  className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs print:shadow-none print:break-inside-avoid scroll-mt-48">
                  {/* Header — always visible, click to collapse */}
                  <button
                    onClick={() => toggleCollapse(result.id)}
                    className="w-full flex items-center justify-between gap-4 px-5 py-4 border-b border-slate-100 bg-slate-50/60 hover:bg-slate-100/60 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-700">
                        {globalIdx}
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-sm font-bold text-slate-900 truncate">
                          {highlightText(result.name_snapshot, searchQuery)}
                        </h3>
                        <p className="text-[10px] text-slate-500 truncate mt-0.5">{result.ai_instructions_snapshot}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`rounded-lg border px-2 py-0.5 text-xs font-bold ${badge.cls}`}>{badge.text}</span>
                      <span className="text-base font-black text-slate-900">
                        {result.score}<span className="text-slate-400 font-semibold text-sm">/{result.max_score}</span>
                      </span>
                      {isCollapsed
                        ? <ChevronDown className="h-4 w-4 text-slate-400" />
                        : <ChevronUp className="h-4 w-4 text-slate-400" />}
                    </div>
                  </button>

                  {/* Score bar */}
                  <div className="h-1.5 bg-slate-100">
                    <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
                  </div>

                  {/* Body — collapsible */}
                  {!isCollapsed && (
                    <div className="px-5 py-4 space-y-3">
                      <div className="flex items-start gap-2">
                        <TrendingUp className="h-3.5 w-3.5 text-slate-400 shrink-0 mt-0.5" />
                        <p className="text-xs leading-relaxed text-slate-800 font-medium">
                          {highlightText(result.reason, searchQuery)}
                        </p>
                      </div>
                      {result.evidence && (
                        <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-3.5">
                          <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-700 uppercase tracking-wider mb-1.5">
                            <Quote className="h-3 w-3" /> Evidence from Transcript
                          </div>
                          <p className="text-xs italic text-indigo-900 leading-relaxed font-medium">
                            "{highlightText(result.evidence, searchQuery)}"
                          </p>
                        </div>
                      )}
                      {result.suggestion && (
                        <div className="flex items-start gap-2.5 rounded-xl bg-teal-50 border border-teal-200 p-3.5">
                          <Lightbulb className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-[10px] font-bold text-teal-700 uppercase tracking-wider mb-0.5">Improvement Tip</p>
                            <p className="text-xs text-teal-950 leading-relaxed font-medium">
                              {highlightText(result.suggestion, searchQuery)}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── EXTRACTION SECTIONS ───────────────────────────────────── */}
      {sectionResults.length > 0 && (
        <div ref={sectionsRef} className="space-y-3 pt-2 scroll-mt-4">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-600" />
            Extracted Call Information
            <span className="text-sm font-semibold text-slate-400">
              ({filteredSections.length}{filteredSections.length !== sectionResults.length ? ` of ${sectionResults.length}` : ""})
            </span>
          </h2>
          {filteredSections.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
              <p className="text-sm font-bold text-slate-500">No sections match your search</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {filteredSections.map((sec) => (
                <div key={sec.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs print:shadow-none print:break-inside-avoid">
                  <h3 className="text-xs font-bold text-indigo-700 flex items-center gap-2 mb-3 uppercase tracking-wider">
                    <FileText className="h-3.5 w-3.5" />
                    {highlightText(sec.name_snapshot, searchQuery)}
                  </h3>
                  <p className="whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-800 bg-slate-50 p-3.5 rounded-xl border border-slate-200 font-medium">
                    {highlightText(sec.extracted_content || "No information extracted.", searchQuery)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── FULL CALL TRANSCRIPT ──────────────────────────────────── */}
      {transcript && (dialogueText || transcript.raw_text) && (
        <div id="transcript-section" ref={transcriptRef} className="rounded-2xl border border-slate-200 bg-white shadow-xs print:shadow-none scroll-mt-24">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <FileText className="h-4 w-4 text-teal-600" /> Full Call Transcript
            </h2>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs print:hidden">
                <button onClick={() => setTranscriptViewMode("dialogue")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${transcriptViewMode === "dialogue" ? "bg-teal-600 text-white" : "text-slate-600 hover:text-slate-900"}`}>
                  <MessageSquare className="h-3 w-3" /> Dialogue
                </button>
                <button onClick={() => setTranscriptViewMode("raw")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-bold transition-all ${transcriptViewMode === "raw" ? "bg-teal-600 text-white" : "text-slate-600 hover:text-slate-900"}`}>
                  <AlignLeft className="h-3 w-3" /> Raw Text
                </button>
              </div>

              {/* Copy Transcript Button */}
              <button
                onClick={handleCopyTranscript}
                className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-teal-400 hover:text-teal-700 transition-all shadow-2xs print:hidden"
                title="Copy transcript text to clipboard"
              >
                {copiedTranscript ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5 text-slate-500" />
                    <span>Copy</span>
                  </>
                )}
              </button>

              <button onClick={() => setTranscriptExpanded(!transcriptExpanded)}
                className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 print:hidden">
                {transcriptExpanded ? <><ChevronUp className="h-3.5 w-3.5" /> Collapse</> : <><ChevronDown className="h-3.5 w-3.5" /> Expand</>}
              </button>
            </div>
          </div>
          <div className={`px-5 py-4 ${!transcriptExpanded ? "max-h-64 overflow-hidden relative" : ""}`}>
            {!transcriptExpanded && (
              <div className="absolute bottom-0 inset-x-0 h-20 bg-gradient-to-t from-white to-transparent z-10 print:hidden" />
            )}
            {transcriptViewMode === "dialogue" && dialogueText
              ? <SpeakerDialogue text={dialogueText} />
              : <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800 whitespace-pre-wrap break-words">
                  {transcript.raw_text || dialogueText}
                </div>}
          </div>
          {!transcriptExpanded && (
            <div className="px-5 pb-4 print:hidden">
              <button onClick={() => setTranscriptExpanded(true)}
                className="flex items-center justify-center gap-1.5 w-full rounded-xl bg-slate-50 border border-slate-200 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 transition-all">
                <ChevronDown className="h-4 w-4" /> Show Full Transcript
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── REPORT FOOTER ─────────────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-5 py-4 flex flex-wrap items-center justify-between gap-4 text-[10px] text-slate-400 font-medium">
        {tokenUsage?.total_tokens && (
          <span className="flex items-center gap-1">
            <Cpu className="h-3 w-3" /> {tokenUsage.total_tokens.toLocaleString()} tokens used
          </span>
        )}
        {llmModelUsed && <span className="font-mono">{llmModelUsed}</span>}
        <div className="flex items-center gap-1 ml-auto">
          <Sparkles className="h-3 w-3" />
          Generated by AI Call Quality System · {reportDate}
        </div>
      </div>
    </div>
  );
}
