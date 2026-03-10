import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Friend Match - 社内友達マッチング',
  description: '社内の仲間と趣味や関心でつながろう',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
