import type { Metadata } from "next";
import "./globals.css";
import Nav from "../components/Nav";
import { Spotlight } from "../components/Fx";

export const metadata: Metadata = {
  title: "Social Poster",
  description: "Upload once. Publish everywhere — via official APIs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Spotlight />
        <Nav />
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
