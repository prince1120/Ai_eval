"use client";

import React, { useState } from "react";
import { Plus, Trash2, ArrowUp, ArrowDown, Sparkles, Layers, ListChecks, BookOpen } from "lucide-react";
import { BPOQASelectorModal } from "./BPOQASelectorModal";

export interface ParameterFormItem {
  id?: string;
  name: string;
  description?: string;
  ai_instructions: string;
  weight?: number;
  min_score: number;
  max_score: number;
  is_required: boolean;
  display_order: number;
}

export interface SectionFormItem {
  id?: string;
  name: string;
  description?: string;
  ai_instructions: string;
  display_order: number;
}

interface DynamicParameterFormProps {
  initialParameters?: ParameterFormItem[];
  initialSections?: SectionFormItem[];
  templateName: string;
  templateDescription?: string;
  onSubmit: (data: {
    name: string;
    description: string;
    parameters: ParameterFormItem[];
    sections: SectionFormItem[];
  }) => Promise<void>;
  isSaving?: boolean;
  onFormChange?: () => void;
}

export function DynamicParameterForm({
  initialParameters = [],
  initialSections = [],
  templateName: initName = "",
  templateDescription: initDesc = "",
  onSubmit,
  isSaving = false,
  onFormChange,
}: DynamicParameterFormProps) {
  const [name, setName] = useState(initName);
  const [description, setDescription] = useState(initDesc);
  const [isLibraryModalOpen, setIsLibraryModalOpen] = useState(false);

  const withClientIds = <T extends { id?: string }>(items: T[]): T[] =>
    items.map((item) => (item.id ? item : { ...item, id: crypto.randomUUID() }));

  const [parameters, setParameters] = useState<ParameterFormItem[]>(
    withClientIds(
      initialParameters.length > 0
        ? initialParameters
        : [
            {
              name: "Politeness & Tone",
              ai_instructions: "Evaluate agent polite greeting, tone of voice, and empathy.",
              weight: 1.0,
              min_score: 0,
              max_score: 10,
              is_required: true,
              display_order: 1,
            },
          ]
    )
  );
  const [sections, setSections] = useState<SectionFormItem[]>(
    withClientIds(
      initialSections.length > 0
        ? initialSections
        : [
            {
              name: "Customer Objections",
              ai_instructions: "Extract explicit customer complaints or objections.",
              display_order: 1,
            },
          ]
    )
  );

  const addParameter = () => {
    setParameters([
      ...parameters,
      {
        id: crypto.randomUUID(),
        name: `Parameter ${parameters.length + 1}`,
        ai_instructions: "Instructions for AI evaluation...",
        weight: 1.0,
        min_score: 0,
        max_score: 10,
        is_required: true,
        display_order: parameters.length + 1,
      },
    ]);
  };

  const removeParameter = (index: number) => {
    setParameters(parameters.filter((_, idx) => idx !== index));
  };

  const moveParameter = (index: number, direction: "up" | "down") => {
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= parameters.length) return;

    const newParams = [...parameters];
    const temp = newParams[index];
    newParams[index] = newParams[targetIdx];
    newParams[targetIdx] = temp;

    newParams.forEach((p, idx) => (p.display_order = idx + 1));
    setParameters(newParams);
  };

  const updateParameterField = (
    index: number,
    field: keyof ParameterFormItem,
    value: any
  ) => {
    const updated = [...parameters];
    updated[index] = { ...updated[index], [field]: value };
    setParameters(updated);
  };

  const addSection = () => {
    setSections([
      ...sections,
      {
        id: crypto.randomUUID(),
        name: `Extraction Section ${sections.length + 1}`,
        ai_instructions: "Instructions for information extraction...",
        display_order: sections.length + 1,
      },
    ]);
  };

  const removeSection = (index: number) => {
    setSections(sections.filter((_, idx) => idx !== index));
  };

  const handleImportFromLibrary = (
    importedParams: ParameterFormItem[],
    importedSections: SectionFormItem[]
  ) => {
    // Append parameters without duplicating identical names
    const existingNames = new Set(parameters.map((p) => p.name.toLowerCase()));
    const newParams = importedParams.filter(
      (p) => !existingNames.has(p.name.toLowerCase())
    );

    const mergedParams = [...parameters, ...withClientIds(newParams)].map((p, idx) => ({
      ...p,
      display_order: idx + 1,
    }));

    // Append sections without duplicating identical names
    const existingSecNames = new Set(sections.map((s) => s.name.toLowerCase()));
    const newSections = importedSections.filter(
      (s) => !existingSecNames.has(s.name.toLowerCase())
    );

    const mergedSections = [...sections, ...withClientIds(newSections)].map((s, idx) => ({
      ...s,
      display_order: idx + 1,
    }));

    setParameters(mergedParams);
    setSections(mergedSections);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({ name, description, parameters, sections });
  };

  return (
    <form onSubmit={handleFormSubmit} className="space-y-8">
      {/* Preset Library Selection Modal */}
      <BPOQASelectorModal
        isOpen={isLibraryModalOpen}
        onClose={() => setIsLibraryModalOpen(false)}
        onImport={handleImportFromLibrary}
      />

      {/* Template Metadata */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-teal-600" />
          Scorecard Metadata
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <label className="block text-xs font-bold text-slate-700">
              Template Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Support Quality Scorecard"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-700">
              Description (Optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Standard evaluation template"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Dynamic Parameters List */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <ListChecks className="h-5 w-5 text-teal-600" />
              Scoring Parameters ({parameters.length})
            </h2>
            <p className="text-xs text-slate-500">
              Build custom criteria by selecting pre-defined BPO parameters or adding custom rules.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsLibraryModalOpen(true)}
              className="flex items-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-4 py-2 text-xs font-bold text-teal-800 shadow-2xs hover:bg-teal-100 transition-all"
            >
              <BookOpen className="h-4 w-4 text-teal-600" /> Add from QA Library
            </button>

            <button
              type="button"
              onClick={addParameter}
              className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-slate-800 transition-all"
            >
              <Plus className="h-4 w-4" /> Add Parameter
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {parameters.map((param, index) => (
            <div
              key={param.id}
              className="group relative rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:border-teal-400 shadow-xs"
            >
              <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                <span className="flex items-center gap-2 text-xs font-mono font-bold text-slate-500">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-teal-50 text-[10px] font-bold text-teal-700 border border-teal-200">
                    {index + 1}
                  </span>
                  Parameter #{index + 1}
                </span>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => moveParameter(index, "up")}
                    className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                    title="Move Up"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    disabled={index === parameters.length - 1}
                    onClick={() => moveParameter(index, "down")}
                    className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                    title="Move Down"
                  >
                    <ArrowDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => removeParameter(index)}
                    className="p-1 text-slate-400 hover:text-rose-600 transition-colors ml-2"
                    title="Delete Parameter"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold text-slate-700">
                    Parameter Name
                  </label>
                  <input
                    type="text"
                    required
                    value={param.name}
                    onChange={(e) =>
                      updateParameterField(index, "name", e.target.value)
                    }
                    placeholder="e.g. Active Listening"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-900 focus:border-teal-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700">
                    Weight
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={param.weight ?? 1.0}
                    onChange={(e) =>
                      updateParameterField(index, "weight", parseFloat(e.target.value) || 1.0)
                    }
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-900 focus:border-teal-500 focus:outline-none"
                  />
                </div>

                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-bold text-slate-700">
                      Min / Max
                    </label>
                    <div className="flex items-center gap-1 mt-1">
                      <input
                        type="number"
                        value={param.min_score}
                        onChange={(e) =>
                          updateParameterField(index, "min_score", parseInt(e.target.value) || 0)
                        }
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-900 text-center font-bold"
                      />
                      <span className="text-slate-400">-</span>
                      <input
                        type="number"
                        value={param.max_score}
                        onChange={(e) =>
                          updateParameterField(index, "max_score", parseInt(e.target.value) || 10)
                        }
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-900 text-center font-bold"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-3">
                <label className="block text-xs font-bold text-slate-700">
                  AI Evaluation Instructions
                </label>
                <textarea
                  rows={2}
                  required
                  value={param.ai_instructions}
                  onChange={(e) =>
                    updateParameterField(index, "ai_instructions", e.target.value)
                  }
                  placeholder="Explain exactly how the AI should score this parameter..."
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-teal-500 focus:outline-none"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dynamic Extraction Sections */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <Layers className="h-5 w-5 text-indigo-600" />
              Custom Extraction Sections ({sections.length})
            </h2>
            <p className="text-xs text-slate-500">
              Extract key insights, objections, competitor mentions, or compliance quotes.
            </p>
          </div>
          <button
            type="button"
            onClick={addSection}
            className="flex items-center gap-2 rounded-xl bg-white border border-slate-200 px-4 py-2 text-xs font-bold text-slate-900 hover:bg-slate-50 transition-all shadow-xs"
          >
            <Plus className="h-4 w-4" /> Add Section
          </button>
        </div>

        <div className="space-y-4">
          {sections.map((sec, index) => (
            <div
              key={sec.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 relative shadow-xs"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-indigo-600">
                  Section #{index + 1}
                </span>
                <button
                  type="button"
                  onClick={() => removeSection(index)}
                  className="text-slate-400 hover:text-rose-600 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700">
                    Section Name
                  </label>
                  <input
                    type="text"
                    required
                    value={sec.name}
                    onChange={(e) => {
                      const updated = [...sections];
                      updated[index].name = e.target.value;
                      setSections(updated);
                    }}
                    placeholder="e.g. Competitor Mentions"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-900 focus:border-teal-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700">
                    AI Extraction Instructions
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={sec.ai_instructions}
                    onChange={(e) => {
                      const updated = [...sections];
                      updated[index].ai_instructions = e.target.value;
                      setSections(updated);
                    }}
                    placeholder="Instructions for AI text extraction..."
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-teal-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          type="submit"
          disabled={isSaving}
          className="flex items-center gap-2 rounded-xl bg-teal-600 px-6 py-3 text-sm font-bold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50 transition-all"
        >
          {isSaving ? "Saving Scorecard..." : "Save Evaluation Scorecard"}
        </button>
      </div>
    </form>
  );
}
