import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Prêches de l'Imam",
  description:
    "Plateforme de transcription et traduction de prêches audio en arabe vers français et anglais.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>
        <header className="topbar">
          <div className="container topbar-inner">
            <Link href="/" className="brand">
              <span className="brand-mark" />
              <div>
                <div className="brand-title">Prêches de l&apos;Imam</div>
                <div className="brand-sub">Transcription &amp; Traduction</div>
              </div>
            </Link>
            <nav className="nav">
              <Link href="/">Bibliothèque</Link>
              <Link href="/upload" className="btn btn-primary">
                + Nouveau prêche
              </Link>
            </nav>
          </div>
        </header>
        <main className="container main">{children}</main>
        <footer className="footer">
          <div className="container">
            <span>© {new Date().getFullYear()} — Prêches de l&apos;Imam</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
