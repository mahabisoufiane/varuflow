"use client";
import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";

interface NpsSurvey {
  id: string;
  survey_type: string;
  triggered_at: string;
}

export function useNps() {
  const [survey, setSurvey] = useState<NpsSurvey | null>(null);

  useEffect(() => {
    // Only fetch once per session to avoid re-triggering after dismiss
    const seenKey = "nps_seen_session";
    if (sessionStorage.getItem(seenKey)) return;

    apiClient
      .get<{ survey: NpsSurvey | null }>("/api/nps/pending")
      .then(({ survey }) => {
        if (survey) {
          setSurvey(survey);
          sessionStorage.setItem(seenKey, "1");
        }
      })
      .catch(() => {/* silently fail — NPS must never break dashboard */});
  }, []);

  function dismiss() {
    setSurvey(null);
  }

  return { survey, dismiss };
}
