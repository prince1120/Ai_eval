"use client";

import React, { useState } from "react";
import { Modal } from "@/components/Modal";
import { BookOpen, CheckCircle2, CheckSquare, Square, ChevronDown, ChevronRight, PlusCircle, Search } from "lucide-react";
import { ParameterFormItem, SectionFormItem } from "./DynamicParameterForm";

export interface PresetCategory {
  categoryName: string;
  parameters: Array<{
    name: string;
    ai_instructions: string;
    weight: number;
    min_score: number;
    max_score: number;
  }>;
}

export const PRESET_CATEGORIES: PresetCategory[] = [
  {
    categoryName: "1. Opening / Greeting",
    parameters: [
      { name: "Greets within expected time", ai_instructions: "Check if agent greeted the caller promptly within the first ring or opening seconds of the call.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Uses standard company greeting script", ai_instructions: "Check if agent used the official brand/company opening greeting script.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "States agent name clearly", ai_instructions: "Check if agent stated their name clearly during the opening introduction.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "States company/department name", ai_instructions: "Check if agent identified company or department name during opening.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Tone is warm and professional", ai_instructions: "Evaluate if agent opening tone was welcoming, polite, warm, and professional.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Confirms customer's name/identity appropriately", ai_instructions: "Check if agent acknowledged and addressed customer by their correct name.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "2. Identity & Verification",
    parameters: [
      { name: "Verifies customer identity per policy", ai_instructions: "Check if agent verified required security credentials (account number, phone, DOB, OTP, etc.).", weight: 2.0, min_score: 0, max_score: 10 },
      { name: "Follows correct verification sequence", ai_instructions: "Check if identity verification steps were followed in the correct logical sequence.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Handles failed verification correctly", ai_instructions: "If customer failed verification, evaluate if agent handled security failure according to protocol.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Maintains data privacy during verification", ai_instructions: "Check if agent maintained strict PII data privacy without leaking sensitive info.", weight: 2.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "3. Active Listening & Needs Assessment",
    parameters: [
      { name: "Asks open-ended discovery questions", ai_instructions: "Evaluate if agent asked effective open questions to understand customer's inquiry.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Lets customer finish speaking without interrupting", ai_instructions: "Check if agent listened patiently without interrupting or talking over the customer.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Paraphrases/confirms understanding of the issue", ai_instructions: "Check if agent summarized or paraphrased the problem to confirm understanding.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Asks relevant probing/follow-up questions", ai_instructions: "Check if agent asked appropriate clarifying or follow-up questions.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Identifies the real/root problem", ai_instructions: "Check if agent uncovered the underlying root cause instead of just addressing surface symptoms.", weight: 2.0, min_score: 0, max_score: 10 },
      { name: "Shows empathy for customer's situation", ai_instructions: "Evaluate if agent expressed genuine empathy, understanding, and care for customer inconvenience.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Avoids asking customer to repeat already-given information", ai_instructions: "Check if agent avoided making customer repeat details already provided.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "4. Problem Diagnosis",
    parameters: [
      { name: "Correctly categorizes the issue type", ai_instructions: "Evaluate if agent correctly diagnosed and categorized the issue.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Uses appropriate tools/systems to investigate", ai_instructions: "Check if agent checked tools, databases, or order records to investigate.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Explains findings back to customer clearly", ai_instructions: "Check if agent clearly communicated diagnostic findings to customer.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Checks account/order/history before responding", ai_instructions: "Check if agent reviewed customer history before suggesting solutions.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Avoids guessing — confirms facts before proceeding", ai_instructions: "Check if agent verified facts accurately rather than guessing or giving speculative answers.", weight: 1.5, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "5. Problem Resolution",
    parameters: [
      { name: "Offers a correct and complete solution", ai_instructions: "Check if agent provided a correct, complete, and accurate resolution.", weight: 2.5, min_score: 0, max_score: 10 },
      { name: "Explains solution steps clearly", ai_instructions: "Evaluate if solution steps and instructions were explained clearly.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Offers alternatives if primary solution isn't available", ai_instructions: "Check if agent offered viable alternative solutions when primary options were unavailable.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Sets accurate expectations (timelines, next steps)", ai_instructions: "Check if agent set realistic resolution timelines and next steps.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Resolves issue on first contact (FCR) where possible", ai_instructions: "Check if issue was resolved completely on the first contact without requiring callbacks.", weight: 2.0, min_score: 0, max_score: 10 },
      { name: "Follows correct escalation process if unresolved", ai_instructions: "If unresolved, check if agent escalated the ticket/issue to correct supervisor/department.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Confirms customer understood/accepted the solution", ai_instructions: "Check if agent confirmed customer agreed with and understood resolution.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Avoids overpromising (no false commitments)", ai_instructions: "Check if agent avoided making false promises or unauthorized commitments.", weight: 2.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "6. Product / Service Knowledge",
    parameters: [
      { name: "Demonstrates accurate product/policy knowledge", ai_instructions: "Evaluate agent subject-matter expertise and policy understanding.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Avoids providing incorrect information", ai_instructions: "Check if agent avoided giving inaccurate, misleading, or outdated information.", weight: 2.0, min_score: 0, max_score: 10 },
      { name: "Cross-sell/upsell attempted where appropriate", ai_instructions: "If relevant, check if agent offered relevant product upgrades or value-add features.", weight: 0.5, min_score: 0, max_score: 10 },
      { name: "Correctly explains pricing/terms/policies", ai_instructions: "Check if agent clearly explained relevant billing, pricing, or contract terms.", weight: 1.5, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "7. Compliance & Risk",
    parameters: [
      { name: "Follows mandatory disclosure/disclaimer script", ai_instructions: "Check if agent read required legal or regulatory disclosure disclaimers.", weight: 3.0, min_score: 0, max_score: 10 },
      { name: "No prohibited language or promises used", ai_instructions: "Check if agent avoided prohibited terms, guarantees, or compliance violations.", weight: 3.0, min_score: 0, max_score: 10 },
      { name: "Handles sensitive/PII data per compliance rules", ai_instructions: "Check if agent handled confidential credit card/PII data securely.", weight: 3.0, min_score: 0, max_score: 10 },
      { name: "Follows recording/consent disclosure if required", ai_instructions: "Check if call recording notification was communicated if applicable.", weight: 2.0, min_score: 0, max_score: 10 },
      { name: "No discriminatory, rude, or inappropriate language", ai_instructions: "Check if agent maintained respectful, non-discriminatory speech.", weight: 3.0, min_score: 0, max_score: 10 },
      { name: "Adheres to industry-specific regulation", ai_instructions: "Check adherence to regulatory rules (FDCPA, RBI, HIPAA, GDPR as applicable).", weight: 3.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "8. Objection & Complaint Handling",
    parameters: [
      { name: "Acknowledges customer frustration/objection", ai_instructions: "Check if agent acknowledged customer complaints or objections politely.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Stays calm and non-defensive under pressure", ai_instructions: "Check if agent remained composed and calm during heated moments.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Offers resolution/de-escalation appropriately", ai_instructions: "Check if agent used effective de-escalation techniques.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Doesn't argue or talk over the customer", ai_instructions: "Check if agent avoided arguing or becoming defensive with customer.", weight: 1.5, min_score: 0, max_score: 10 },
      { name: "Manages competitor mentions professionally", ai_instructions: "Check if agent handled competitor mentions objectively and professionally.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "9. Communication Quality",
    parameters: [
      { name: "Clear speech pace and pronunciation", ai_instructions: "Evaluate agent clarity, pace, and clarity of speech.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Uses simple, jargon-free language", ai_instructions: "Check if agent used clear, jargon-free explanations.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Maintains professional tone throughout", ai_instructions: "Evaluate if professional demeanor was maintained across the full call duration.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Appropriate hold/mute usage with notice given", ai_instructions: "Check if agent asked permission before placing customer on hold/mute.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Minimal dead air / silence gaps", ai_instructions: "Check if agent avoided awkward long periods of unannounced silence.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "10. Call Control & Efficiency",
    parameters: [
      { name: "Manages call duration efficiently", ai_instructions: "Check if agent handled conversation efficiently without unnecessary padding.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Keeps conversation on-track without rambling", ai_instructions: "Check if agent guided call flow constructively.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Avoids unnecessary transfers", ai_instructions: "Check if agent avoided unnecessary call transfers.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Handles multitasking without losing engagement", ai_instructions: "Check if agent maintained verbal engagement during system lookups.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
  {
    categoryName: "11. Closing",
    parameters: [
      { name: "Summarizes resolution/next steps before ending", ai_instructions: "Check if agent recapped agreed action items before closing.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Asks if there's anything else needed", ai_instructions: "Check if agent asked 'Is there anything else I can assist you with today?'.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Confirms follow-up action/ticket if applicable", ai_instructions: "Check if ticket numbers or follow-up details were confirmed.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Thanks customer / proper closing script used", ai_instructions: "Check if agent thanked customer and used proper closing branding script.", weight: 1.0, min_score: 0, max_score: 10 },
      { name: "Ends call only after customer confirms satisfaction", ai_instructions: "Check if agent waited for customer confirmation before disconnecting.", weight: 1.0, min_score: 0, max_score: 10 },
    ],
  },
];

export const PRESET_SECTIONS = [
  { name: "Customer Sentiment", ai_instructions: "Extract customer sentiment progression from beginning to end of call (e.g. Frustrated -> Satisfied)." },
  { name: "Call Outcome", ai_instructions: "Determine final call outcome: Resolved, Escalated, or Unresolved." },
  { name: "Reason for Call", ai_instructions: "Extract primary customer inquiry category and root cause complaint." },
  { name: "Competitor Mentions", ai_instructions: "Extract any competitor brand names or service comparisons stated by customer." },
  { name: "Follow-Up Action Required", ai_instructions: "Extract required follow-up tasks, callback promises, or open ticket numbers." },
  { name: "Agent Talk-Time Ratio", ai_instructions: "Estimate agent vs customer talk-time proportion and engagement balance." },
];

interface BPOQASelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (selectedParams: ParameterFormItem[], selectedSections: SectionFormItem[]) => void;
}

export function BPOQASelectorModal({ isOpen, onClose, onImport }: BPOQASelectorModalProps) {
  const [selectedParamNames, setSelectedParamNames] = useState<string[]>([]);
  const [selectedSectionNames, setSelectedSectionNames] = useState<string[]>([]);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    "1. Opening / Greeting": true,
    "2. Identity & Verification": true,
  });
  const [searchQuery, setSearchQuery] = useState("");

  const toggleCategory = (catName: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [catName]: !prev[catName],
    }));
  };

  const toggleParam = (pName: string) => {
    setSelectedParamNames((prev) =>
      prev.includes(pName) ? prev.filter((name) => name !== pName) : [...prev, pName]
    );
  };

  const toggleSection = (sName: string) => {
    setSelectedSectionNames((prev) =>
      prev.includes(sName) ? prev.filter((name) => name !== sName) : [...prev, sName]
    );
  };

  const toggleAllInCategory = (category: PresetCategory) => {
    const allNames = category.parameters.map((p) => p.name);
    const allSelected = allNames.every((n) => selectedParamNames.includes(n));

    if (allSelected) {
      setSelectedParamNames((prev) => prev.filter((n) => !allNames.includes(n)));
    } else {
      setSelectedParamNames((prev) => Array.from(new Set([...prev, ...allNames])));
    }
  };

  const handleImportSelected = () => {
    const paramsToImport: ParameterFormItem[] = [];
    PRESET_CATEGORIES.forEach((cat) => {
      cat.parameters.forEach((p) => {
        if (selectedParamNames.includes(p.name)) {
          paramsToImport.push({
            name: p.name,
            ai_instructions: p.ai_instructions,
            weight: p.weight,
            min_score: p.min_score,
            max_score: p.max_score,
            is_required: true,
            display_order: paramsToImport.length + 1,
          });
        }
      });
    });

    const sectionsToImport: SectionFormItem[] = [];
    PRESET_SECTIONS.forEach((s) => {
      if (selectedSectionNames.includes(s.name)) {
        sectionsToImport.push({
          name: s.name,
          ai_instructions: s.ai_instructions,
          display_order: sectionsToImport.length + 1,
        });
      }
    });

    onImport(paramsToImport, sectionsToImport);
    onClose();
  };

  const selectAll59 = () => {
    const allP = PRESET_CATEGORIES.flatMap((c) => c.parameters.map((p) => p.name));
    const allS = PRESET_SECTIONS.map((s) => s.name);
    setSelectedParamNames(allP);
    setSelectedSectionNames(allS);
  };

  const clearAllSelection = () => {
    setSelectedParamNames([]);
    setSelectedSectionNames([]);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="mx-auto w-full max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-2xl space-y-6 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-teal-600" /> BPO Call Center QA Preset Library
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Select specific call stage parameters and sections to add into your template
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={selectAll59}
              className="rounded-xl border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-bold text-teal-800 hover:bg-teal-100"
            >
              Select All (59)
            </button>
            <button
              type="button"
              onClick={clearAllSelection}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-100"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Live Filter Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search criteria (e.g. greeting, verification, solution, closing)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
          />
        </div>

        {/* Categorized List Container */}
        <div className="overflow-y-auto flex-1 space-y-4 pr-1">
          {PRESET_CATEGORIES.map((cat) => {
            const filteredParams = cat.parameters.filter(
              (p) =>
                p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                p.ai_instructions.toLowerCase().includes(searchQuery.toLowerCase())
            );

            if (searchQuery && filteredParams.length === 0) return null;

            const isExpanded = expandedCategories[cat.categoryName] ?? !!searchQuery;
            const catParamNames = cat.parameters.map((p) => p.name);
            const allSelectedInCat = catParamNames.every((n) => selectedParamNames.includes(n));
            const someSelectedInCat = catParamNames.some((n) => selectedParamNames.includes(n));

            return (
              <div
                key={cat.categoryName}
                className="rounded-2xl border border-slate-200 bg-slate-50/50 overflow-hidden shadow-2xs"
              >
                {/* Category Header */}
                <div
                  onClick={() => toggleCategory(cat.categoryName)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggleCategory(cat.categoryName);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  className="flex items-center justify-between bg-slate-100 px-4 py-3 cursor-pointer select-none border-b border-slate-200/60"
                >
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleAllInCategory(cat);
                      }}
                      className="text-slate-500 hover:text-slate-900"
                    >
                      {allSelectedInCat ? (
                        <CheckSquare className="h-4 w-4 text-teal-600" />
                      ) : someSelectedInCat ? (
                        <CheckSquare className="h-4 w-4 text-teal-500/60" />
                      ) : (
                        <Square className="h-4 w-4 text-slate-400" />
                      )}
                    </button>
                    <span className="text-xs font-bold text-slate-900">
                      {cat.categoryName} ({cat.parameters.length})
                    </span>
                  </div>

                  <span className="text-slate-400 hover:text-slate-900">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </span>
                </div>

                {/* Category Parameters */}
                {isExpanded && (
                  <div className="p-3 space-y-2 bg-white">
                    {filteredParams.map((p) => {
                      const isSelected = selectedParamNames.includes(p.name);

                      return (
                        <div
                          key={p.name}
                          onClick={() => toggleParam(p.name)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              toggleParam(p.name);
                            }
                          }}
                          role="checkbox"
                          aria-checked={isSelected}
                          tabIndex={0}
                          className={`flex items-start gap-3 rounded-xl border p-3 cursor-pointer transition-all ${
                            isSelected
                              ? "border-teal-400 bg-teal-50/40 shadow-2xs"
                              : "border-slate-200 hover:border-slate-300"
                          }`}
                        >
                          <button type="button" className="mt-0.5 text-slate-400">
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4 text-teal-600" />
                            ) : (
                              <Square className="h-4 w-4 text-slate-300" />
                            )}
                          </button>

                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-slate-900">{p.name}</span>
                              <span className="text-[10px] font-mono text-slate-500 font-semibold bg-slate-100 px-2 py-0.5 rounded">
                                W: {p.weight} | Range: 0-{p.max_score}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1 font-mono">
                              {p.ai_instructions}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {/* Metadata Extraction Sections Category */}
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50/30 overflow-hidden shadow-2xs">
            <div className="bg-indigo-100/60 px-4 py-3 border-b border-indigo-200/60">
              <span className="text-xs font-bold text-indigo-950">
                12. Extracted Metadata Sections ({PRESET_SECTIONS.length})
              </span>
            </div>

            <div className="p-3 space-y-2 bg-white">
              {PRESET_SECTIONS.map((s) => {
                const isSelected = selectedSectionNames.includes(s.name);

                return (
                  <div
                    key={s.name}
                    onClick={() => toggleSection(s.name)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleSection(s.name);
                      }
                    }}
                    role="checkbox"
                    aria-checked={isSelected}
                    tabIndex={0}
                    className={`flex items-start gap-3 rounded-xl border p-3 cursor-pointer transition-all ${
                      isSelected
                        ? "border-indigo-400 bg-indigo-50/40 shadow-2xs"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <button type="button" className="mt-0.5 text-slate-400">
                      {isSelected ? (
                        <CheckSquare className="h-4 w-4 text-indigo-600" />
                      ) : (
                        <Square className="h-4 w-4 text-slate-300" />
                      )}
                    </button>

                    <div className="flex-1">
                      <span className="text-xs font-bold text-slate-900">{s.name}</span>
                      <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1 font-mono">
                        {s.ai_instructions}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-200">
          <p className="text-xs font-bold text-slate-700">
            Selected: <span className="text-teal-700 font-extrabold">{selectedParamNames.length} Parameters</span> + <span className="text-indigo-700 font-extrabold">{selectedSectionNames.length} Sections</span>
          </p>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={selectedParamNames.length === 0 && selectedSectionNames.length === 0}
              onClick={handleImportSelected}
              className="rounded-xl bg-teal-600 px-5 py-2 text-xs font-bold text-white shadow-xs hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5"
            >
              <PlusCircle className="h-4 w-4" /> Add Selected to Scorecard
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
