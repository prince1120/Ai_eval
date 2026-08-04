"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Modal } from "@/components/Modal";
import { TemplatesSkeleton } from "@/components/TemplatesSkeleton";
import { Sliders, Plus, CheckCircle2, Edit3, Trash2, Layers, AlertTriangle, Star, Eye, Sparkles, Award, Loader2 } from "lucide-react";

export default function TemplatesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [templateToDelete, setTemplateToDelete] = useState<any | null>(null);
  const [seedError, setSeedError] = useState("");

  const { data: templates = [], isLoading } = useQuery<any[]>({
    queryKey: ["templates"],
    queryFn: () => apiFetch("/templates"),
  });

  const activateMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/templates/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/templates/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setTemplateToDelete(null);
    },
  });

  const createBlankTemplateMutation = useMutation({
    mutationFn: () =>
      apiFetch("/templates", {
        method: "POST",
        body: JSON.stringify({
          name: "New Evaluation Scorecard",
          description: "Custom evaluation criteria and parameters",
          parameters: [
            {
              name: "Customer Greeting & Tone",
              ai_instructions: "Check if agent greeted caller politely with empathetic tone.",
              weight: 1.0,
              min_score: 0,
              max_score: 10,
            },
          ],
        }),
      }),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      router.push(`/templates/${data.id}/edit`);
    },
  });

  const seedBpoPresetMutation = useMutation({
    mutationFn: () =>
      apiFetch("/templates/seed-bpo-preset", {
        method: "POST",
      }),
    onSuccess: (data: any) => {
      setSeedError("");
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      router.push(`/templates/${data.id}/edit`);
    },
    onError: (err: any) => {
      setSeedError(err.message || "Failed to seed BPO QA Master Template");
    },
  });

  return (
    <div className="page-transition mx-auto max-w-7xl px-4 sm:px-6 py-8 space-y-8">
      {/* Delete Confirmation Modal using Portal */}
      <Modal isOpen={!!templateToDelete} onClose={() => setTemplateToDelete(null)}>
        <div className="mx-auto max-w-md rounded-2xl border border-rose-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-rose-600">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <h3 className="text-lg font-bold text-slate-900">Delete Template?</h3>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            Are you sure you want to delete template <strong className="text-slate-900">&quot;{templateToDelete?.name}&quot;</strong> (v{templateToDelete?.version})? This action cannot be undone.
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => setTemplateToDelete(null)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate(templateToDelete.id)}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 shadow-xs disabled:opacity-50"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete Template"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Evaluation Templates
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Define dynamic scorecards, parameter weights, and section extraction rules
          </p>
        </div>

        {isAdmin && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3 w-full sm:w-auto">
            <button
              onClick={() => seedBpoPresetMutation.mutate()}
              disabled={seedBpoPresetMutation.isPending || createBlankTemplateMutation.isPending}
              className="flex items-center justify-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-4 py-2.5 text-xs font-bold text-teal-800 shadow-xs hover:bg-teal-100 transition-all disabled:opacity-50 w-full sm:w-auto"
            >
              {seedBpoPresetMutation.isPending ? (
                <Loader2 className="h-4 w-4 text-teal-600 animate-spin" />
              ) : (
                <Award className="h-4 w-4 text-teal-600" />
              )}
              {seedBpoPresetMutation.isPending ? "Loading BPO Framework..." : "Load BPO 59-Param QA Framework"}
            </button>

            <button
              onClick={() => createBlankTemplateMutation.mutate()}
              disabled={createBlankTemplateMutation.isPending || seedBpoPresetMutation.isPending}
              className="flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4.5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-slate-800 transition-all disabled:opacity-50 w-full sm:w-auto"
            >
              {createBlankTemplateMutation.isPending ? (
                <Loader2 className="h-4 w-4 text-white animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {createBlankTemplateMutation.isPending ? "Creating Template..." : "Create Custom Template"}
            </button>
          </div>
        )}
      </div>

      {seedError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs font-semibold text-rose-700">
          {seedError}
        </div>
      )}

      {/* Templates Grid */}
      {isLoading ? (
        <TemplatesSkeleton />
      ) : templates.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-xs space-y-4">
          <Award className="mx-auto h-12 w-12 text-teal-500 mb-2" />
          <div>
            <h3 className="text-base font-bold text-slate-900">No Templates Defined</h3>
            <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
              Load our pre-built 59-Parameter BPO QA Master Framework or build custom criteria.
            </p>
          </div>

          {isAdmin && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={() => seedBpoPresetMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl bg-teal-600 text-white font-bold px-4 py-2.5 text-xs shadow-xs hover:bg-teal-700"
              >
                <Award className="h-4 w-4" /> Load BPO 59-Param QA Framework
              </button>

              <button
                onClick={() => createBlankTemplateMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 text-white font-bold px-4 py-2.5 text-xs shadow-xs hover:bg-slate-800"
              >
                <Plus className="h-4 w-4" /> Blank Custom Template
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className={`flex flex-col justify-between rounded-2xl border p-6 transition-all shadow-xs ${
                tpl.is_active
                  ? "border-teal-500 bg-white ring-2 ring-teal-500/20"
                  : "border-slate-200 bg-white hover:border-slate-400"
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[10px] font-mono font-bold text-slate-600">
                    v{tpl.version}
                  </span>
                  {tpl.is_active ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 border border-emerald-200">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> Default Scorecard
                    </span>
                  ) : isAdmin ? (
                    <button
                      onClick={() => activateMutation.mutate(tpl.id)}
                      disabled={activateMutation.isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-slate-50 border border-slate-200 px-2.5 py-1 text-xs font-bold text-slate-900 hover:bg-slate-100 transition-all"
                      title="Make this template your default scorecard for new transcript evaluations"
                    >
                      <Star className="h-3 w-3 text-slate-600" /> Set as Default
                    </button>
                  ) : null}
                </div>

                <h3 className="mt-4 text-lg font-bold text-slate-900">{tpl.name}</h3>
                <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                  {tpl.description || "No description provided"}
                </p>

                <div className="mt-6 flex items-center gap-4 text-xs text-slate-600 border-t border-slate-100 pt-4 font-semibold">
                  <span className="flex items-center gap-1">
                    <Sliders className="h-3.5 w-3.5 text-teal-600" />
                    {tpl.parameters.length} Parameters
                  </span>
                  <span className="flex items-center gap-1">
                    <Layers className="h-3.5 w-3.5 text-indigo-600" />
                    {tpl.sections.length} Sections
                  </span>
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4">
                {isAdmin ? (
                  <>
                    <button
                      onClick={() => setTemplateToDelete(tpl)}
                      className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 transition-all"
                      title="Delete Template"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </button>

                    <Link
                      href={`/templates/${tpl.id}/edit`}
                      className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-1.5 text-xs font-bold text-slate-900 hover:border-slate-400 hover:bg-slate-100 transition-all"
                    >
                      <Edit3 className="h-3.5 w-3.5" /> Configure
                    </Link>
                  </>
                ) : (
                  <Link
                    href={`/templates/${tpl.id}/edit`}
                    className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-1.5 text-xs font-bold text-slate-900 hover:border-slate-400 hover:bg-slate-100 transition-all ml-auto"
                  >
                    <Eye className="h-3.5 w-3.5 text-teal-600" /> View Criteria
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
