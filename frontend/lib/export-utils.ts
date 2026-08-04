const CSV_FORMULA_PREFIXES = ["=", "+", "-", "@"];

function csvCell(value: unknown): string {
  let str = String(value ?? "");
  if (CSV_FORMULA_PREFIXES.some((prefix) => str.startsWith(prefix))) {
    str = `'${str}`;
  }
  return `"${str.replace(/"/g, '""')}"`;
}

function getGradeLabel(score: number | null): string {
  if (score === null) return "N/A";
  if (score >= 90) return "Excellent";
  if (score >= 75) return "Good";
  if (score >= 60) return "Average";
  if (score >= 40) return "Needs Improvement";
  return "Poor";
}

function getPassFail(score: number, maxScore: number): string {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  if (pct >= 80) return "Pass";
  if (pct >= 60) return "Average";
  return "Fail";
}

export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

interface ReportMeta {
  templateName?: string;
  templateVersion?: number;
}

export function exportSingleRunToJSON(run: any, transcript?: any, meta?: ReportMeta) {
  const templateName = meta?.templateName || run.template_name || "Call Quality Scorecard";
  const templateVersion = meta?.templateVersion || run.template_version;
  const callRef = transcript?.source_call_id || "Call Recording";
  const grade = getGradeLabel(run.overall_score);

  const data = {
    report_title: "Call Quality Assurance Report",
    report_generated_at: new Date().toISOString(),

    call_information: {
      call_reference: callRef,
      upload_date: transcript?.created_at ? new Date(transcript.created_at).toLocaleString() : "N/A",
      evaluation_date: new Date(run.completed_at || run.created_at).toLocaleString(),
      evaluator: run.creator
        ? run.creator.full_name || run.creator.email?.split("@")[0] || "AI System"
        : "AI System",
    },

    scorecard_summary: {
      template_name: templateName,
      template_version: templateVersion ? `v${templateVersion}` : undefined,
      ai_model: run.llm_model_used || "AI Model",
      overall_score: run.overall_score !== null ? `${run.overall_score.toFixed(1)}%` : "N/A",
      overall_grade: grade,
      total_parameters: (run.parameter_results || []).length,
      parameters_passed: (run.parameter_results || []).filter(
        (p: any) => p.max_score > 0 && (p.score / p.max_score) >= 0.8
      ).length,
      parameters_failed: (run.parameter_results || []).filter(
        (p: any) => p.max_score > 0 && (p.score / p.max_score) < 0.6
      ).length,
    },

    parameter_evaluations: (run.parameter_results || []).map((p: any) => ({
      parameter_name: p.name_snapshot,
      evaluation_criteria: p.ai_instructions_snapshot,
      score: p.score,
      max_score: p.max_score,
      score_percentage: p.max_score > 0 ? `${((p.score / p.max_score) * 100).toFixed(0)}%` : "N/A",
      pass_fail_status: getPassFail(p.score, p.max_score),
      ai_reasoning: p.reason,
      evidence_from_transcript: p.evidence || "N/A",
      improvement_suggestion: p.suggestion || "N/A",
    })),

    extracted_call_information: (run.section_results || []).map((s: any) => ({
      section_name: s.name_snapshot,
      extracted_content: s.extracted_content,
    })),

    token_usage: run.token_usage || {},

    call_transcript: transcript?.raw_text || "",
  };

  const fileRef = callRef.replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `call_qa_report_${fileRef}_${new Date().toISOString().split("T")[0]}.json`;
  downloadFile(JSON.stringify(data, null, 2), filename, "application/json");
}

export function exportSingleRunToCSV(run: any, transcript?: any, meta?: ReportMeta) {
  const templateName = meta?.templateName || run.template_name || "Call Quality Scorecard";
  const templateVersion = meta?.templateVersion || run.template_version;
  const callRef = transcript?.source_call_id || "Call Recording";
  const evaluatorName = run.creator
    ? run.creator.full_name || run.creator.email?.split("@")[0] || "AI System"
    : "AI System";
  const grade = getGradeLabel(run.overall_score);

  const scorePct = run.overall_score !== null ? `${run.overall_score.toFixed(1)}%` : "N/A";
  const evalDate = new Date(run.completed_at || run.created_at).toLocaleString();
  const totalParams = (run.parameter_results || []).length;
  const passCount = (run.parameter_results || []).filter(
    (p: any) => p.max_score > 0 && (p.score / p.max_score) >= 0.8
  ).length;
  const failCount = (run.parameter_results || []).filter(
    (p: any) => p.max_score > 0 && (p.score / p.max_score) < 0.6
  ).length;

  // ── Report Header Block ──
  const headerBlock = [
    `"CALL QUALITY ASSURANCE REPORT"`,
    `"Generated: ${new Date().toLocaleString()}"`,
    `""`,
    `"CALL INFORMATION"`,
    `"Call Reference",${csvCell(callRef)}`,
    `"Evaluation Date",${csvCell(evalDate)}`,
    `"Evaluator",${csvCell(evaluatorName)}`,
    `""`,
    `"SCORECARD SUMMARY"`,
    `"Template",${csvCell(templateName + (templateVersion ? ` v${templateVersion}` : ""))}`,
    `"AI Model",${csvCell(run.llm_model_used || "AI Model")}`,
    `"Overall Score",${csvCell(scorePct)}`,
    `"Overall Grade",${csvCell(grade)}`,
    `"Total Parameters",${totalParams}`,
    `"Parameters Passed",${passCount}`,
    `"Parameters Failed",${failCount}`,
    `""`,
  ];

  // ── Parameter Results Table ──
  const paramHeaders = [
    "Parameter Name",
    "Score",
    "Max Score",
    "Score %",
    "Pass/Fail",
    "AI Reasoning",
    "Evidence Quote",
    "Improvement Suggestion",
  ].join(",");

  const paramRows = (run.parameter_results || []).map((p: any) => {
    const pct = p.max_score > 0 ? `${((p.score / p.max_score) * 100).toFixed(0)}%` : "N/A";
    return [
      csvCell(p.name_snapshot || ""),
      p.score,
      p.max_score,
      csvCell(pct),
      csvCell(getPassFail(p.score, p.max_score)),
      csvCell(p.reason || ""),
      csvCell(p.evidence || "N/A"),
      csvCell(p.suggestion || "N/A"),
    ].join(",");
  });

  // ── Extracted Sections ──
  const sectionsBlock = (run.section_results || []).length > 0
    ? [
        `""`,
        `"EXTRACTED CALL INFORMATION"`,
        `"Section Name","Extracted Content"`,
        ...(run.section_results || []).map((s: any) =>
          `${csvCell(s.name_snapshot || "")},${csvCell(s.extracted_content || "")}`
        ),
      ]
    : [];

  // ── Full Transcript ──
  const transcriptBlock = transcript?.raw_text
    ? [
        `""`,
        `"FULL CALL TRANSCRIPT"`,
        csvCell(transcript.raw_text),
      ]
    : [];

  const csvContent = [
    ...headerBlock,
    `"PARAMETER EVALUATIONS"`,
    paramHeaders,
    ...paramRows,
    ...sectionsBlock,
    ...transcriptBlock,
  ].join("\n");

  const fileRef = callRef.replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `call_qa_report_${fileRef}_${new Date().toISOString().split("T")[0]}.csv`;
  downloadFile(csvContent, filename, "text/csv;charset=utf-8;");
}

export function exportBulkRunsToCSV(runs: any[], transcriptsMap: Record<string, any> = {}) {
  const headers = [
    "Call Reference",
    "Evaluation Date",
    "Evaluator",
    "Template",
    "Overall Score (%)",
    "Overall Grade",
    "Status",
    "Parameters Passed",
    "Parameters Failed",
    "Parameter Score Breakdown",
  ];

  const rows = runs.map((r) => {
    const t = transcriptsMap[r.transcript_id];
    const evaluatorName = r.creator
      ? r.creator.full_name || r.creator.email?.split("@")[0] || "AI System"
      : "AI System";
    const grade = getGradeLabel(r.overall_score);
    const passCount = (r.parameter_results || []).filter(
      (p: any) => p.max_score > 0 && (p.score / p.max_score) >= 0.8
    ).length;
    const failCount = (r.parameter_results || []).filter(
      (p: any) => p.max_score > 0 && (p.score / p.max_score) < 0.6
    ).length;
    const paramScoresStr = (r.parameter_results || [])
      .map((p: any) => `${p.name_snapshot}: ${p.score}/${p.max_score} (${getPassFail(p.score, p.max_score)})`)
      .join(" | ");

    return [
      csvCell(t?.source_call_id || "Call Recording"),
      csvCell(new Date(r.created_at).toLocaleString()),
      csvCell(evaluatorName),
      csvCell(r.template_name || "Scorecard"),
      r.overall_score !== null ? `${r.overall_score.toFixed(1)}%` : "N/A",
      csvCell(grade),
      csvCell(r.status),
      passCount,
      failCount,
      csvCell(paramScoresStr),
    ].join(",");
  });

  const dateStr = new Date().toISOString().split("T")[0];
  const csvContent = [
    `"CALL QUALITY EVALUATION — BULK EXPORT — Generated: ${new Date().toLocaleString()}"`,
    `""`,
    headers.join(","),
    ...rows,
  ].join("\n");

  const filename = `call_qa_bulk_report_${dateStr}.csv`;
  downloadFile(csvContent, filename, "text/csv;charset=utf-8;");
}
