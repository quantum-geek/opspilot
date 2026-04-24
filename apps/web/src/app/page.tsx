"use client";

import { useEffect, useState } from "react";

interface IncidentSummary {
  incident_id: string;
  title: string;
  severity: string;
  status: string;
  duration_minutes: number | null;
  affected_services: string[];
  summary: string;
  root_cause: string | null;
  resolution: string | null;
  runbooks: string[];
  responders: string[];
  labels: string[];
}

interface IncidentAnalysis {
  incident_id: string;
  likely_cause: string;
  recommended_steps: string[];
  recommended_runbook: string | null;
  escalation_targets: string[];
  reasoning_summary: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/incidents/INC-001/summary`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setSummary)
      .catch((err: unknown) =>
        setSummaryError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setSummaryLoading(false));
  }, []);

  function runAnalysis() {
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysis(null);
    fetch(`${API_URL}/incidents/INC-001/analysis`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setAnalysis)
      .catch((err: unknown) =>
        setAnalysisError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setAnalysisLoading(false));
  }

  return (
    <main style={{ fontFamily: "monospace", padding: "2rem", maxWidth: "720px" }}>
      <h1>OpsPilot</h1>

      {summaryLoading && <p style={{ color: "#888" }}>Loading incident summary…</p>}

      {summaryError && (
        <p style={{ color: "#c00", border: "1px solid #c00", padding: "0.75rem" }}>
          Error: {summaryError}
        </p>
      )}

      {summary && (
        <section style={{ marginTop: "1.5rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "baseline", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>{summary.title}</h2>
            <span style={{ fontSize: "0.85rem", background: "#f4f4f4", padding: "2px 8px" }}>
              {summary.severity}
            </span>
            <span style={{ fontSize: "0.85rem", background: "#f4f4f4", padding: "2px 8px" }}>
              {summary.status}
            </span>
            {summary.duration_minutes != null && (
              <span style={{ fontSize: "0.85rem", color: "#666" }}>
                {summary.duration_minutes} min
              </span>
            )}
          </div>

          <p style={{ marginTop: "1rem" }}>{summary.summary}</p>

          {summary.root_cause && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Root cause</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{summary.root_cause}</p>
            </div>
          )}

          {summary.resolution && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Resolution</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{summary.resolution}</p>
            </div>
          )}

          <div style={{ marginTop: "1rem" }}>
            <strong>Affected services</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{summary.affected_services.join(", ")}</p>
          </div>

          {summary.responders.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Responders</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{summary.responders.join(", ")}</p>
            </div>
          )}

          {summary.labels.length > 0 && (
            <div style={{ marginTop: "1rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {summary.labels.map((label) => (
                <span key={label} style={{ fontSize: "0.75rem", background: "#eee", padding: "2px 6px" }}>
                  {label}
                </span>
              ))}
            </div>
          )}

          {summary.runbooks.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Runbooks</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {summary.runbooks.map((rb) => (
                  <li key={rb}>{rb}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Analyze button */}
          <div style={{ marginTop: "1.5rem" }}>
            <button
              onClick={runAnalysis}
              disabled={analysisLoading}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: analysisLoading ? "not-allowed" : "pointer",
                background: "#111",
                color: "#fff",
                border: "none",
              }}
            >
              {analysisLoading ? "Analyzing…" : "Analyze Incident"}
            </button>
          </div>
        </section>
      )}

      {/* Analysis results */}
      {analysisError && (
        <p style={{ marginTop: "1rem", color: "#c00", border: "1px solid #c00", padding: "0.75rem" }}>
          Analysis error: {analysisError}
        </p>
      )}

      {analysis && (
        <section
          style={{
            marginTop: "2rem",
            borderTop: "2px solid #111",
            paddingTop: "1.5rem",
          }}
        >
          <h2 style={{ margin: "0 0 1rem" }}>Analysis</h2>

          <div>
            <strong>Likely cause</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{analysis.likely_cause}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Reasoning</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{analysis.reasoning_summary}</p>
          </div>

          {analysis.recommended_runbook && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Recommended runbook</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{analysis.recommended_runbook}</p>
            </div>
          )}

          {analysis.recommended_steps.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Recommended steps</strong>
              <ol style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {analysis.recommended_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {analysis.escalation_targets.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Escalation targets</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{analysis.escalation_targets.join(", ")}</p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
