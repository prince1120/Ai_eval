"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { DynamicParameterForm } from "@/components/DynamicParameterForm";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export default function TemplateEditPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const templateId = params.id as string;

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
      // If version bumped, redirect to new version template edit URL
      if (updatedTpl.id !== templateId) {
        router.push(`/templates/${updatedTpl.id}/edit`);
      }
    },
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12">
        <div className="h-96 rounded-3xl bg-slate-900/50 animate-pulse border border-slate-800" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-12 text-center text-slate-400">
        Template not found.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/templates"
          className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Templates
        </Link>

        {template.is_active && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Editing Active Version (v{template.version}) — Saving will create v{template.version + 1}
          </span>
        )}
      </div>

      <DynamicParameterForm
        templateName={template.name}
        templateDescription={template.description || ""}
        initialParameters={template.parameters}
        initialSections={template.sections}
        isSaving={updateMutation.isPending}
        onSubmit={async (data) => {
          await updateMutation.mutateAsync(data);
        }}
      />
    </div>
  );
}
