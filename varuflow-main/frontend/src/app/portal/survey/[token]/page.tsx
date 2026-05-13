"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

interface SurveyView { reference_type: string; submitted: boolean; score: number | null; }

export default function SurveyPage() {
  const { token } = useParams<{ token: string }>();
  const [survey, setSurvey] = useState<SurveyView | null>(null);
  const [score, setScore] = useState<number>(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/after-sales/surveys/view/${token}`)
      .then(r => r.json())
      .then(setSurvey)
      .catch(() => {});
  }, [token]);

  const submit = async () => {
    if (!score) { toast.error("Please select a score"); return; }
    setSubmitting(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/after-sales/surveys/submit/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score, comment: comment || null }),
      });
      setDone(true);
    } catch {
      toast.error("Failed to submit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!survey) return <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading…</div>;

  if (survey.submitted || done) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-2">
          <div className="text-4xl">🙏</div>
          <h1 className="text-lg font-bold">Thank you!</h1>
          <p className="text-sm text-gray-500">Your feedback has been recorded.</p>
        </div>
      </div>
    );
  }

  const label = survey.reference_type === "invoice" ? "your recent purchase" : survey.reference_type === "project" ? "your completed project" : "your appointment";

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-lg border shadow-sm p-8 max-w-md w-full space-y-6">
        <div className="space-y-1">
          <h1 className="text-xl font-bold">How did we do?</h1>
          <p className="text-sm text-gray-500">Share your experience with {label}.</p>
        </div>
        <div>
          <p className="text-sm font-medium mb-2">Overall satisfaction</p>
          <div className="flex gap-3">
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                onClick={() => setScore(n)}
                className={`w-10 h-10 rounded-full border-2 text-sm font-bold transition-colors ${
                  score === n ? "bg-[#1a2332] text-white border-[#1a2332]" : "border-gray-300 hover:border-gray-500"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1 px-1">
            <span>Poor</span><span>Excellent</span>
          </div>
        </div>
        <div>
          <label className="text-sm font-medium">Comments (optional)</label>
          <textarea
            className="mt-1 w-full border rounded px-3 py-2 text-sm"
            rows={3}
            placeholder="What could we improve?"
            value={comment}
            onChange={e => setComment(e.target.value)}
          />
        </div>
        <button
          onClick={submit}
          disabled={submitting || !score}
          className="w-full py-2.5 bg-[#1a2332] text-white rounded font-medium hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit Feedback"}
        </button>
      </div>
    </div>
  );
}
