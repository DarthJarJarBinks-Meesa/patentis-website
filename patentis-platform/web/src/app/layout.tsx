import './globals.css';
import Link from 'next/link';

export const metadata = {
  title: 'Patentis Platform',
  description: 'Innovation intelligence for R&D teams',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav>
          <strong>Patentis</strong>
          <Link href="/">Home</Link>
          <Link href="/landscape">Landscape</Link>
          <Link href="/projects">Corpus</Link>
          <Link href="/calibration">Calibration</Link>
          <Link href="/agents">Agents</Link>
          <Link href="/login">Login</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
