import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OpsPilot",
  description: "AI-powered incident response platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
