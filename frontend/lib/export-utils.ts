const CSV_FORMULA_PREFIXES = ["=", "+", "-", "@"];

function csvCell(value: unknown): string {
  let str = String(value ?? "");
  if (CSV_FORMULA_PREFIXES.some((prefix) => str.startsWith(prefix))) {
    str = `'${str}`;
  }
  return `"${str.replace(/"/g, '""')}"`;
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

export function exportSingleRunToJSON(run: any, transcript?: any) {
  const data = {
    report_title: "Call Quality Evaluation Report",
    source_call: transcript?.source_call_id || "Call Recording",
    evaluated_date: new Date(run.completed_at || run.created_at).toLocaleString(),
    overall_quality_score: run.overall_score !== null ? `${run.overall_score.toFixed(1)}%` : "N/A",
    parameter_evaluations: (run.parameter_results || []).map((p: any) => ({
      parameter_name: p.name_snapshot,
      instructions: p.ai_instructions_snapshot,
      score: `${p.score} / ${p.max_score}`,
      ai_reasoning: p.reason,
      evidence_quote: p.evidence || "N/A",
      improvement_suggestion: p.suggestion || "N/A",
    })),
    extracted_sections: (run.section_results || []).map((s: any) => ({
      section_name: s.name_snapshot,
      extracted_content: s.extracted_content,
    })),
    call_transcript: transcript?.raw_text || "",
  };

  const callRef = (transcript?.source_call_id || "report").replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `call_quality_report_${callRef}.json`;
  downloadFile(JSON.stringify(data, null, 2), filename, "application/json");
}

export function exportSingleRunToCSV(run: any, transcript?: any) {
  const headers = ["Parameter Name", "Score", "Max Score", "AI Reason & Explanation", "Evidence Quote", "Improvement Suggestion"];
  const rows = (run.parameter_results || []).map((p: any) => [
    csvCell(p.name_snapshot || ""),
    p.score,
    p.max_score,
    csvCell(p.reason || ""),
    csvCell(p.evidence || "N/A"),
    csvCell(p.suggestion || "N/A"),
  ]);

  const sectionsRows = (run.section_results || []).map((s: any) => [
    csvCell(`Section: ${s.name_snapshot || ""}`),
    '""',
    '""',
    csvCell(s.extracted_content || ""),
    '""',
    '""',
  ]);

  const csvContent = [
    `"Call Quality Evaluation Report"`,
    csvCell(`Call Reference: ${transcript?.source_call_id || "Call Recording"}`),
    `"Overall Score: ${run.overall_score !== null ? run.overall_score.toFixed(1) + "%" : "N/A"}"`,
    `"Evaluated Date: ${new Date(run.created_at).toLocaleString()}"`,
    "",
    headers.join(","),
    ...rows.map((r: any) => r.join(",")),
    "",
    `"Extracted Section Insights"`,
    ...sectionsRows.map((r: any) => r.join(",")),
  ].join("\n");

  const callRef = (transcript?.source_call_id || "report").replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `call_quality_report_${callRef}.csv`;
  downloadFile(csvContent, filename, "text/csv;charset=utf-8;");
}

export function exportBulkRunsToCSV(runs: any[], transcriptsMap: Record<string, any> = {}) {
  const headers = [
    "Call Reference",
    "Evaluated Date",
    "Overall Score (%)",
    "Status",
    "Parameter Scores Breakdown",
  ];

  const rows = runs.map((r) => {
    const t = transcriptsMap[r.transcript_id];
    const paramScoresStr = (r.parameter_results || [])
      .map((p: any) => `${p.name_snapshot}: ${p.score}/${p.max_score}`)
      .join(" | ");

    return [
      csvCell(t?.source_call_id || "Call Recording"),
      `"${new Date(r.created_at).toLocaleString()}"`,
      r.overall_score !== null ? `${r.overall_score.toFixed(1)}%` : "N/A",
      `"${r.status}"`,
      csvCell(paramScoresStr),
    ];
  });

  const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `evaluation_reports_summary_${dateStr}.csv`;
  downloadFile(csvContent, filename, "text/csv;charset=utf-8;");
}
