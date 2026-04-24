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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [data, setData] = useState<IncidentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/incidents/INC-001/summary`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Unknown error")
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <main style={{ fontFamily: "monospace", padding: "2rem", maxWidth: "720px" }}>
      <h1>OpsPilot</h1>

      {loading && <p style={{ color: "#888" }}>Loading incident summary…</p>}

      {error && (
        <p style={{ color: "#c00", border: "1px solid #c00", padding: "0.75rem" }}>
          Error: {error}
        </p>
      )}

      {data && (
        <section style={{ marginTop: "1.5rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "baseline", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>{data.title}</h2>
            <span style={{ fontSize: "0.85rem", background: "#f4f4f4", padding: "2px 8px" }}>
              {data.severity}
            </span>
            <span style={{ fontSize: "0.85rem", background: "#f4f4f4", padding: "2px 8px" }}>
              {data.status}
            </span>
            {data.duration_minutes != null && (
              <span style={{ fontSize: "0.85rem", color: "#666" }}>
                {data.duration_minutes} min
              </span>
            )}
          </div>

          <p style={{ marginTop: "1rem" }}>{data.summary}</p>

          {data.root_cause && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Root cause</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{data.root_cause}</p>
            </div>
          )}

          {data.resolution && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Resolution</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{data.resolution}</p>
            </div>
          )}

          <div style={{ marginTop: "1rem" }}>
            <strong>Affected services</strong>
            <p style={{ margin: "0.25rem 0 0" }}>{data.affected_services.join(", ")}</p>
          </div>

          {data.responders.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Responders</strong>
              <p style={{ margin: "0.25rem 0 0" }}>{data.responders.join(", ")}</p>
            </div>
          )}

          {data.labels.length > 0 && (
            <div style={{ marginTop: "1rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {data.labels.map((label) => (
                <span
                  key={label}
                  style={{
                    fontSize: "0.75rem",
                    background: "#eee",
                    padding: "2px 6px",
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          )}

          {data.runbooks.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <strong>Runbooks</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                {data.runbooks.map((rb) => (
                  <li key={rb}>{rb}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
