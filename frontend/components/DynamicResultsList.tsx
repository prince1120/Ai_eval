"use client";

import React, { useState } from "react";
import {
  Award,
  CheckCircle2,
  Quote,
  Lightbulb,
  Search,
  Layers,
  FileText,
  Sparkles,
  UserCheck,
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
}

export function DynamicResultsList({
  overallScore,
  parameterResults = [],
  sectionResults = [],
  llmModelUsed,
  creator,
  tokenUsage,
}: DynamicResultsListProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredParameters = parameterResults.filter((p) =>
    p.name_snapshot.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.reason.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getScoreBadgeColor = (score: number, maxScore: number) => {
    const pct = (score / maxScore) * 100;
    if (pct >= 80) return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (pct >= 60) return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-rose-50 text-rose-700 border-rose-200";
  };

  return (
    <div className="space-y-8">
      {/* Scorecard Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-8 shadow-xs">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-700 border border-teal-200">
                <Sparkles className="h-3.5 w-3.5" /> Evaluation Completed
              </span>

              {creator && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 border border-indigo-200">
                  <UserCheck className="h-3.5 w-3.5 text-indigo-600" />
                  Evaluated by: {creator.full_name || creator.email.split("@")[0]} ({creator.email})
                </span>
              )}
            </div>

            <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-900">
              Transcript Scorecard
            </h1>
            {tokenUsage?.total_tokens && (
              <p className="mt-1 font-mono text-xs text-teal-700 font-bold">
                Tokens: {tokenUsage.total_tokens}
              </p>
            )}
          </div>

          {overallScore !== null && (
            <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-4 shadow-inner">
              <div className="text-right">
                <span className="block text-xs uppercase tracking-wider text-slate-500 font-bold">
                  Overall Score
                </span>
                <span className="text-4xl font-black text-teal-600">
                  {overallScore.toFixed(1)}%
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Parameter Results */}
      <div className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-teal-600" />
            Parameter Evaluations ({parameterResults.length})
          </h2>

          {parameterResults.length > 5 && (
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Filter parameters..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
              />
            </div>
          )}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {filteredParameters.map((result) => (
            <div
              key={result.id}
              className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:border-teal-400 shadow-xs"
            >
              <div>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      {result.name_snapshot}
                    </h3>
                    <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                      {result.ai_instructions_snapshot}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-bold border ${getScoreBadgeColor(
                      result.score,
                      result.max_score
                    )}`}
                  >
                    {result.score} / {result.max_score}
                  </span>
                </div>

                <p className="mt-4 text-xs leading-relaxed text-slate-800 font-medium">
                  {result.reason}
                </p>

                {result.evidence && (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-700 uppercase tracking-wider">
                      <Quote className="h-3 w-3" /> Evidence Quote
                    </div>
                    <p className="mt-1 text-xs italic text-slate-600 font-medium">
                      &quot;{result.evidence}&quot;
                    </p>
                  </div>
                )}
              </div>

              {result.suggestion && (
                <div className="mt-4 flex items-start gap-2 rounded-xl bg-teal-50 border border-teal-200 p-3.5">
                  <Lightbulb className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
                  <p className="text-xs text-teal-950 font-medium">{result.suggestion}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Extraction Sections */}
      {sectionResults.length > 0 && (
        <div className="space-y-4 pt-4 border-t border-slate-200">
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="h-5 w-5 text-indigo-600" />
            Extracted Insights & Sections ({sectionResults.length})
          </h2>

          <div className="grid gap-4 md:grid-cols-2">
            {sectionResults.map((sec) => (
              <div
                key={sec.id}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
              >
                <h3 className="text-sm font-bold text-indigo-700 flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {sec.name_snapshot}
                </h3>
                <p className="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-slate-800 bg-slate-50/80 p-4 rounded-xl border border-slate-200 font-medium">
                  {sec.extracted_content || "No information extracted."}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
