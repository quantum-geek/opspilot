export default function Home() {
  return (
    <main style={{ fontFamily: "monospace", padding: "2rem" }}>
      <h1>OpsPilot</h1>
      <p>AI-powered incident response platform — Week 1 scaffold.</p>
      <ul>
        <li>
          API:{" "}
          <a href={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}>
            {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
          </a>
        </li>
      </ul>
    </main>
  );
}
