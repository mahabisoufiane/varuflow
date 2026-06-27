"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

declare global {
  interface Window {
    posthog?: { capture: (event: string, props?: object) => void };
  }
}

interface Props {
  survey: {
    id: string;
    survey_type: string;
    triggered_at: string;
  };
  onDismiss: () => void;
  onSubmit: () => void;
}

function getQuestion(survey_type: string): string {
  switch (survey_type) {
    case "day_30":
      return "How would you rate Varuflow after your first month?";
    case "day_90":
      return "How likely are you to recommend Varuflow to a colleague?";
    case "cancellation":
      return "Before you go — how would you rate your experience?";
    case "quarterly":
      return "How satisfied are you with Varuflow this quarter?";
    default:
      return "How likely are you to recommend Varuflow? (0 = Not at all, 10 = Definitely)";
  }
}

function getCategory(score: number): "promoter" | "passive" | "detractor" {
  if (score >= 9) return "promoter";
  if (score >= 7) return "passive";
  return "detractor";
}

export default function NpsSurveyModal({ survey, onDismiss, onSubmit }: Props) {
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Fire shown event once on mount
  useState(() => {
    window.posthog?.capture("nps_shown", { survey_type: survey.survey_type });
  });

  async function handleSubmit() {
    if (selectedScore === null) return;
    setSubmitting(true);
    try {
      await apiClient.post("/api/nps/respond", {
        survey_id: survey.id,
        score: selectedScore,
        comment: comment.trim() || undefined,
      });
      const category = getCategory(selectedScore);
      window.posthog?.capture("nps_submitted", { score: selectedScore, category });
      setSubmitted(true);
      onSubmit();
    } catch {
      toast.error("Failed to submit feedback. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDismiss() {
    try {
      await apiClient.post("/api/nps/dismiss", { survey_id: survey.id });
    } catch {
      // silently ignore — dismiss should never block the user
    }
    window.posthog?.capture("nps_dismissed", { survey_type: survey.survey_type });
    onDismiss();
  }

  const category = selectedScore !== null ? getCategory(selectedScore) : null;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-full max-w-sm sm:max-w-sm max-sm:bottom-0 max-sm:right-0 max-sm:left-0 max-sm:max-w-full">
      <div className="bg-[#0f172a] border border-indigo-500/30 rounded-xl shadow-2xl shadow-indigo-500/10 p-5 relative">
        {/* Indigo border glow */}
        <div className="absolute inset-0 rounded-xl ring-1 ring-inset ring-indigo-500/20 pointer-events-none" />

        {/* Close button */}
        <button
          onClick={handleDismiss}
          className="absolute top-3 right-3 text-slate-400 hover:text-slate-200 transition-colors"
          aria-label="Close survey"
        >
          <X size={16} />
        </button>

        {!submitted ? (
          <>
            {/* Header */}
            <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">
              Quick question
            </p>

            {/* Question */}
            <p className="text-sm text-slate-200 font-medium mb-4 pr-4">
              {getQuestion(survey.survey_type)}
            </p>

            {/* Score selector */}
            <div className="flex gap-1 mb-1">
              {Array.from({ length: 11 }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedScore(i)}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded transition-all ${
                    selectedScore === i
                      ? "bg-indigo-600 text-white ring-2 ring-indigo-400"
                      : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                  }`}
                >
                  {i}
                </button>
              ))}
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 mb-4">
              <span>Not at all</span>
              <span>Definitely</span>
            </div>

            {/* Comment textarea — only after score selected */}
            {selectedScore !== null && (
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Any additional thoughts? (optional)"
                rows={2}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
              />
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={selectedScore === null || submitting}
              className="w-full py-2 rounded-lg text-sm font-semibold transition-all bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed mb-2"
            >
              {submitting ? "Submitting…" : "Submit feedback"}
            </button>

            {/* Dismiss link */}
            <button
              onClick={handleDismiss}
              className="w-full text-center text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Dismiss
            </button>
          </>
        ) : (
          /* Thank-you state */
          <div className="py-2">
            {category === "promoter" && (
              <>
                <p className="text-sm font-semibold text-slate-200 mb-3">
                  🎉 Thank you! Would you leave us a quick review?
                </p>
                <div className="flex gap-2">
                  <a
                    href="https://www.g2.com/products/varuflow/reviews"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 text-center text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 transition-colors"
                  >
                    Review on G2
                  </a>
                  <a
                    href="https://www.capterra.com/p/varuflow"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 text-center text-xs font-semibold rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
                  >
                    Review on Capterra
                  </a>
                </div>
              </>
            )}

            {category === "passive" && (
              <p className="text-sm text-slate-200">
                Thanks for your feedback! What would make Varuflow a 9 or 10 for you?
              </p>
            )}

            {category === "detractor" && (
              <>
                <p className="text-sm text-slate-200 mb-3">
                  We&apos;re sorry you&apos;re having a tough time. Can we jump on a quick call?
                </p>
                <a
                  href="https://calendly.com/varuflow/support"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full py-2 text-center text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 transition-colors"
                >
                  Book a call
                </a>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
