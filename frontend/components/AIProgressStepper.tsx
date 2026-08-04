"use client";

import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  Loader2,
  Cpu,
  Sparkles,
  Database,
  Globe,
  MessageSquare,
  ShieldCheck,
  Clock,
} from "lucide-react";

interface AIProgressStepperProps {
  status: "pending" | "processing" | "done" | "failed";
}

export function AIProgressStepper({ status }: AIProgressStepperProps) {
  const [activeStep, setActiveStep] = useState(1);
  const [secondsElapsed, setSecondsElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsElapsed((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (status === "pending") {
      setActiveStep(1);
    } else if (status === "processing") {
      const stepTimer1 = setTimeout(() => setActiveStep(2), 2000);
      const stepTimer2 = setTimeout(() => setActiveStep(3), 5000);
      const stepTimer3 = setTimeout(() => setActiveStep(4), 8000);

      return () => {
        clearTimeout(stepTimer1);
        clearTimeout(stepTimer2);
        clearTimeout(stepTimer3);
      };
    } else if (status === "done") {
      setActiveStep(4);
    }
  }, [status]);

  const steps = [
    {
      id: 1,
      title: "Audio Storage & Integrity",
      desc: "Call recording saved to MinIO object storage",
      icon: Database,
    },
    {
      id: 2,
      title: "Groq Whisper STT & Language Detection",
      desc: "Transcribing audio & identifying spoken languages",
      icon: Globe,
    },
    {
      id: 3,
      title: "Mistral Speaker Diarization",
      desc: "Separating Agent vs Customer dialogue turns",
      icon: MessageSquare,
    },
    {
      id: 4,
      title: "Scorecard Parameter Evaluation",
      desc: "Evaluating quality parameters & extracting key insights",
      icon: Cpu,
    },
  ];

  const formatElapsed = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m > 0 ? `${m}m ` : ""}${s}s`;
  };

  return (
    <div className="rounded-3xl border border-teal-200/80 bg-gradient-to-b from-teal-50/60 via-white to-slate-50 p-6 sm:p-8 space-y-6 shadow-md">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-md">
            <Sparkles className="h-6 w-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold text-slate-900">AI Quality Analysis Engine</h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-teal-100 px-2.5 py-0.5 text-[10px] font-extrabold text-teal-800 uppercase tracking-wider">
                <Loader2 className="h-3 w-3 animate-spin" /> In Progress
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Evaluating call against active compliance scorecard...
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-xl bg-white border border-slate-200 px-3.5 py-2 text-xs font-bold text-slate-700 shadow-2xs self-start sm:self-auto">
          <Clock className="h-4 w-4 text-teal-600 animate-spin" />
          Elapsed Time: <span className="font-mono text-teal-700">{formatElapsed(secondsElapsed)}</span>
        </div>
      </div>

      {/* Stepper list */}
      <div className="space-y-4">
        {steps.map((step) => {
          const isDone = activeStep > step.id || status === "done";
          const isCurrent = activeStep === step.id && status !== "done";
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={`flex items-start gap-4 rounded-2xl p-4 transition-all border ${
                isDone
                  ? "border-emerald-200 bg-emerald-50/50"
                  : isCurrent
                  ? "border-teal-300 bg-white shadow-sm ring-2 ring-teal-500/20"
                  : "border-slate-100 bg-slate-50/50 opacity-60"
              }`}
            >
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all ${
                  isDone
                    ? "bg-emerald-600 text-white"
                    : isCurrent
                    ? "bg-teal-600 text-white shadow-md"
                    : "bg-slate-200 text-slate-500"
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : isCurrent ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Icon className="h-5 w-5" />
                )}
              </div>

              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3
                    className={`text-sm font-bold ${
                      isDone
                        ? "text-emerald-950"
                        : isCurrent
                        ? "text-slate-900"
                        : "text-slate-500"
                    }`}
                  >
                    {step.title}
                  </h3>
                  {isDone && (
                    <span className="text-[10px] font-extrabold text-emerald-700 uppercase tracking-wider bg-emerald-100 px-2 py-0.5 rounded-md">
                      Completed
                    </span>
                  )}
                  {isCurrent && (
                    <span className="text-[10px] font-extrabold text-teal-700 uppercase tracking-wider bg-teal-100 px-2 py-0.5 rounded-md animate-pulse">
                      Processing...
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5 font-medium">{step.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
