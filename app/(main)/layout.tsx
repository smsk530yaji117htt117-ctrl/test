'use client'

import NavBar from '@/components/NavBar'

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="md:ml-56 pb-20 md:pb-8">
        {children}
      </main>
    </div>
  )
}
