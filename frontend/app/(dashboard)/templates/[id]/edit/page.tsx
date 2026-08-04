"use client";

import React, { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { DynamicParameterForm } from "@/components/DynamicParameterForm";
import { Modal } from "@/components/Modal";
import { TemplateEditSkeleton } from "@/components/TemplateEditSkeleton";
import { useToast } from "@/components/Toast";
import { ArrowLeft, CheckCircle2, AlertTriangle, Save, Trash2, X, Loader2 } from "lucide-react";
import Link from "next/link";

export default function TemplateEditPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const templateId = params.id as string;

  const [isDirty, setIsDirty] = useState(false);
  const [isExitModalOpen, setIsExitModalOpen] = useState(false);
  const formRef = useRef<any>(null);

  const { data: template, isLoading } = useQuery<any>({
    queryKey: ["template", templateId],
    queryFn: () => apiFetch(`/templates/${templateId}`),
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) =>
      apiFetch(`/templates/${templateId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: (updatedTpl: any) => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      queryClient.invalidateQueries({ queryKey: ["template", templateId] });
      setIsDirty(false);
    },
  });

  const deleteDraftMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/templates/${templateId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
  });

  // ── Intercept Browser Back Button, Mouse Gesture, & Tab Reload ─────
  useEffect(() => {
    if (!template) return;
    const isNewDraft = template.name === "New Evaluation Scorecard";

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty || isNewDraft) {
        e.preventDefault();
        e.returnValue = "";
      }
    };

    // Push state so back button can be intercepted
    window.history.pushState({ page: "template-edit" }, "", window.location.href);

    const handlePopState = (e: PopStateEvent) => {
      if (isDirty || isNewDraft) {
        window.history.pushState({ page: "template-edit" }, "", window.location.href);
        setIsExitModalOpen(true);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("popstate", handlePopState);
    };
  }, [template, isDirty]);

  const handleBackClick = (e: React.MouseEvent) => {
    e.preventDefault();
    const isNewDraft = template?.name === "New Evaluation Scorecard";
    if (isDirty || isNewDraft) {
      setIsExitModalOpen(true);
    } else {
      router.push("/templates");
    }
  };

  const handleDiscardAndExit = async () => {
    try {
      await deleteDraftMutation.mutateAsync();
      showToast("Template draft discarded and removed.", "info");
    } catch (e) {
      // Ignore if already deleted
    }
    setIsExitModalOpen(false);
    router.push("/templates");
  };

  if (isLoading) {
    return <TemplateEditSkeleton />;
  }

  if (!template) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12 text-center text-slate-500 font-semibold">
        Template not found.
      </div>
    );
  }

  const isNewDraft = template.name === "New Evaluation Scorecard";

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 space-y-6 animate-in fade-in duration-300">
      {/* Exit Prompt Modal */}
      <Modal isOpen={isExitModalOpen} onClose={() => setIsExitModalOpen(false)}>
        <div className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5">
          <div className="flex items-center gap-3 text-amber-600">
            <div className="p-2.5 rounded-2xl bg-amber-50 border border-amber-200">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">Unsaved Scorecard Draft</h3>
              <p className="text-xs text-slate-500 font-medium">What would you like to do before leaving?</p>
            </div>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-2xl border border-slate-200">
            {isNewDraft
              ? "You opened a new custom template draft. Discarding will delete this scorecard so it does not clutter your template list."
              : "You have unsaved edits on this scorecard template."}
          </p>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2.5 pt-2">
            <button
              onClick={() => setIsExitModalOpen(false)}
              className="rounded-xl px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Keep Editing
            </button>

            <button
              disabled={deleteDraftMutation.isPending}
              onClick={handleDiscardAndExit}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-bold text-rose-700 hover:bg-rose-600 hover:text-white transition-all disabled:opacity-50"
            >
              {deleteDraftMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Discard & Delete Draft
            </button>
          </div>
        </div>
      </Modal>

      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleBackClick}
          className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Templates
        </button>

        {template.is_active && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800 border border-emerald-200 shadow-2xs">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> Default Scorecard (v{template.version}) — Saving creates v{template.version + 1}
          </span>
        )}
      </div>

      <DynamicParameterForm
        templateName={template.name}
        templateDescription={template.description || ""}
        initialParameters={template.parameters}
        initialSections={template.sections}
        isSaving={updateMutation.isPending}
        onFormChange={() => setIsDirty(true)}
        onSubmit={async (data) => {
          const updated = await updateMutation.mutateAsync(data);
          showToast("Scorecard template saved successfully!", "success");
          if (updated && updated.id !== templateId) {
            router.push(`/templates/${updated.id}/edit`);
          } else {
            router.push("/templates");
          }
        }}
      />
    </div>
  );
}
