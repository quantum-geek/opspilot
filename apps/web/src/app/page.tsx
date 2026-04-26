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
  analysis_source?: "llm" | "fallback";
}

interface AuditEvent {
  incident_id: string;
  artifact_type: string;
  source: string;
  action: string;
  timestamp: string;
}

interface PostmortemDraft {
  incident_id: string;
  title: string;
  summary: string;
  impact: string;
  timeline: string[];
  root_cause: string;
  resolution: string;
  follow_ups: string[];
  draft_source?: "llm" | "fallback";
}

interface StakeholderUpdate {
  incident_id: string;
  audience: string;
  subject: string;
  update_text: string;
  status: string;
  impact_summary: string;
  next_steps: string[];
  draft_source?: "llm" | "fallback";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const [stakeholderUpdate, setStakeholderUpdate] = useState<StakeholderUpdate | null>(null);
  const [stakeholderLoading, setStakeholderLoading] = useState(false);
  const [stakeholderError, setStakeholderError] = useState<string | null>(null);

  const [postmortem, setPostmortem] = useState<PostmortemDraft | null>(null);
  const [postmortemLoading, setPostmortemLoading] = useState(false);
  const [postmortemError, setPostmortemError] = useState<string | null>(null);

  const [stakeholderApproval, setStakeholderApproval] = useState<"approved" | "rejected" | null>(null);
  const [stakeholderApprovalError, setStakeholderApprovalError] = useState<string | null>(null);
  const [postmortemApproval, setPostmortemApproval] = useState<"approved" | "rejected" | null>(null);
  const [postmortemApprovalError, setPostmortemApprovalError] = useState<string | null>(null);

  const [auditEvents, setAuditEvents] = useState<AuditEvent[] | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

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

  function draftStakeholderUpdate() {
    setStakeholderLoading(true);
    setStakeholderError(null);
    setStakeholderUpdate(null);
    setStakeholderApproval(null);
    setStakeholderApprovalError(null);
    fetch(`${API_URL}/incidents/INC-001/stakeholder-update`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setStakeholderUpdate)
      .catch((err: unknown) =>
        setStakeholderError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setStakeholderLoading(false));
  }

  function generatePostmortem() {
    setPostmortemLoading(true);
    setPostmortemError(null);
    setPostmortem(null);
    setPostmortemApproval(null);
    setPostmortemApprovalError(null);
    fetch(`${API_URL}/incidents/INC-001/postmortem-draft`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setPostmortem)
      .catch((err: unknown) =>
        setPostmortemError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setPostmortemLoading(false));
  }

  function handleApproval(
    artifact: "stakeholder-update" | "postmortem-draft",
    action: "approve" | "reject"
  ) {
    const setApproval = artifact === "stakeholder-update" ? setStakeholderApproval : setPostmortemApproval;
    const setError = artifact === "stakeholder-update" ? setStakeholderApprovalError : setPostmortemApprovalError;
    setError(null);
    fetch(`${API_URL}/incidents/INC-001/${artifact}/${action}`, { method: "POST" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(() => setApproval(action === "approve" ? "approved" : "rejected"))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unknown error"));
  }

  function loadAuditHistory() {
    setAuditLoading(true);
    setAuditError(null);
    fetch(`${API_URL}/incidents/INC-001/audit`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { events: AuditEvent[] }) => setAuditEvents(data.events))
      .catch((err: unknown) => setAuditError(err instanceof Error ? err.message : "Unknown error"))
      .finally(() => setAuditLoading(false));
  }

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
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Analysis</h2>
            {analysis.analysis_source && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 6px",
                  background: analysis.analysis_source === "llm" ? "#d4edda" : "#f4f4f4",
                  color: analysis.analysis_source === "llm" ? "#155724" : "#555",
                  border: `1px solid ${analysis.analysis_source === "llm" ? "#c3e6cb" : "#ccc"}`,
                }}
              >
                {analysis.analysis_source === "llm" ? "LLM analysis" : "fallback"}
              </span>
            )}
          </div>

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

          <div style={{ marginTop: "1.5rem" }}>
            <button
              onClick={draftStakeholderUpdate}
              disabled={stakeholderLoading}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: stakeholderLoading ? "not-allowed" : "pointer",
                background: "#111",
                color: "#fff",
                border: "none",
              }}
            >
              {stakeholderLoading ? "Drafting…" : "Draft Stakeholder Update"}
            </button>
          </div>
        </section>
      )}

      {stakeholderError && (
        <p style={{ marginTop: "1rem", color: "#c00", border: "1px solid #c00", padding: "0.75rem" }}>
          Stakeholder update error: {stakeholderError}
        </p>
      )}

      {stakeholderUpdate && (
        <section
          style={{
            marginTop: "2rem",
            borderTop: "2px solid #111",
            paddingTop: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Stakeholder Update</h2>
            {stakeholderUpdate.draft_source && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 6px",
                  background: stakeholderUpdate.draft_source === "llm" ? "#d4edda" : "#f4f4f4",
                  color: stakeholderUpdate.draft_source === "llm" ? "#155724" : "#555",
                  border: `1px solid ${stakeholderUpdate.draft_source === "llm" ? "#c3e6cb" : "#ccc"}`,
                }}
              >
                {stakeholderUpdate.draft_source === "llm" ? "LLM draft" : "fallback"}
              </span>
            )}
          </div>

          <div>
            <strong>To</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{stakeholderUpdate.audience}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Subject</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{stakeholderUpdate.subject}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Impact</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{stakeholderUpdate.impact_summary}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Update</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{stakeholderUpdate.update_text}</p>
          </div>

          {stakeholderUpdate.next_steps.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Next steps</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {stakeholderUpdate.next_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <button
              onClick={() => handleApproval("stakeholder-update", "approve")}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: "pointer",
                background: stakeholderApproval === "approved" ? "#155724" : "#fff",
                color: stakeholderApproval === "approved" ? "#fff" : "#111",
                border: "1px solid #111",
              }}
            >
              Approve
            </button>
            <button
              onClick={() => handleApproval("stakeholder-update", "reject")}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: "pointer",
                background: stakeholderApproval === "rejected" ? "#721c24" : "#fff",
                color: stakeholderApproval === "rejected" ? "#fff" : "#111",
                border: "1px solid #111",
              }}
            >
              Reject
            </button>
            {stakeholderApproval && (
              <span style={{ fontSize: "0.85rem", color: stakeholderApproval === "approved" ? "#155724" : "#721c24" }}>
                {stakeholderApproval === "approved" ? "Approved" : "Rejected"}
              </span>
            )}
            {stakeholderApprovalError && (
              <span style={{ fontSize: "0.85rem", color: "#c00" }}>{stakeholderApprovalError}</span>
            )}
          </div>

          <div style={{ marginTop: "1rem" }}>
            <button
              onClick={generatePostmortem}
              disabled={postmortemLoading}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: postmortemLoading ? "not-allowed" : "pointer",
                background: "#111",
                color: "#fff",
                border: "none",
              }}
            >
              {postmortemLoading ? "Generating…" : "Generate Postmortem Draft"}
            </button>
          </div>
        </section>
      )}

      {postmortemError && (
        <p style={{ marginTop: "1rem", color: "#c00", border: "1px solid #c00", padding: "0.75rem" }}>
          Postmortem error: {postmortemError}
        </p>
      )}

      {postmortem && (
        <section
          style={{
            marginTop: "2rem",
            borderTop: "2px solid #111",
            paddingTop: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Postmortem Draft</h2>
            {postmortem.draft_source && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 6px",
                  background: postmortem.draft_source === "llm" ? "#d4edda" : "#f4f4f4",
                  color: postmortem.draft_source === "llm" ? "#155724" : "#555",
                  border: `1px solid ${postmortem.draft_source === "llm" ? "#c3e6cb" : "#ccc"}`,
                }}
              >
                {postmortem.draft_source === "llm" ? "LLM draft" : "fallback"}
              </span>
            )}
          </div>

          <div>
            <strong>Title</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{postmortem.title}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Summary</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{postmortem.summary}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Impact</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{postmortem.impact}</p>
          </div>

          {postmortem.timeline.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Timeline</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {postmortem.timeline.map((event, i) => (
                  <li key={i}>{event}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ marginTop: "1rem" }}>
            <strong>Root cause</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{postmortem.root_cause}</p>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <strong>Resolution</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{postmortem.resolution}</p>
          </div>

          {postmortem.follow_ups.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Follow-ups</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {postmortem.follow_ups.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <button
              onClick={() => handleApproval("postmortem-draft", "approve")}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: "pointer",
                background: postmortemApproval === "approved" ? "#155724" : "#fff",
                color: postmortemApproval === "approved" ? "#fff" : "#111",
                border: "1px solid #111",
              }}
            >
              Approve
            </button>
            <button
              onClick={() => handleApproval("postmortem-draft", "reject")}
              style={{
                fontFamily: "monospace",
                fontSize: "0.9rem",
                padding: "0.5rem 1.25rem",
                cursor: "pointer",
                background: postmortemApproval === "rejected" ? "#721c24" : "#fff",
                color: postmortemApproval === "rejected" ? "#fff" : "#111",
                border: "1px solid #111",
              }}
            >
              Reject
            </button>
            {postmortemApproval && (
              <span style={{ fontSize: "0.85rem", color: postmortemApproval === "approved" ? "#155724" : "#721c24" }}>
                {postmortemApproval === "approved" ? "Approved" : "Rejected"}
              </span>
            )}
            {postmortemApprovalError && (
              <span style={{ fontSize: "0.85rem", color: "#c00" }}>{postmortemApprovalError}</span>
            )}
          </div>
        </section>
      )}

      {/* Audit history */}
      <section
        style={{
          marginTop: "2rem",
          borderTop: "2px solid #111",
          paddingTop: "1.5rem",
        }}
      >
        <h2 style={{ margin: "0 0 1rem" }}>Audit History</h2>
        <button
          onClick={loadAuditHistory}
          disabled={auditLoading}
          style={{
            fontFamily: "monospace",
            fontSize: "0.9rem",
            padding: "0.5rem 1.25rem",
            cursor: auditLoading ? "not-allowed" : "pointer",
            background: "#111",
            color: "#fff",
            border: "none",
          }}
        >
          {auditLoading ? "Loading…" : "Load Audit History"}
        </button>

        {auditError && (
          <p style={{ marginTop: "0.75rem", color: "#c00" }}>Error: {auditError}</p>
        )}

        {auditEvents !== null && auditEvents.length === 0 && (
          <p style={{ marginTop: "0.75rem", color: "#888" }}>No audit events recorded yet.</p>
        )}

        {auditEvents && auditEvents.length > 0 && (
          <table style={{ marginTop: "0.75rem", width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr>
                {["Timestamp", "Artifact", "Action", "Source"].map((h) => (
                  <th key={h} style={{ textAlign: "left", borderBottom: "1px solid #ccc", paddingBottom: "0.25rem", paddingRight: "1rem" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {auditEvents.map((ev, i) => (
                <tr key={i}>
                  <td style={{ padding: "0.25rem 1rem 0.25rem 0", color: "#555" }}>{ev.timestamp.replace("T", " ").replace("Z", " UTC")}</td>
                  <td style={{ padding: "0.25rem 1rem 0.25rem 0" }}>{ev.artifact_type}</td>
                  <td style={{ padding: "0.25rem 1rem 0.25rem 0", color: ev.action === "approved" ? "#155724" : ev.action === "rejected" ? "#721c24" : "#111" }}>
                    {ev.action}
                  </td>
                  <td style={{ padding: "0.25rem 0" }}>{ev.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
