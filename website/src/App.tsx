import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LEGAL_PAGES } from './content/legalPages'
import { HomePage } from './pages/HomePage'
import { LegalPage } from './pages/LegalPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        {LEGAL_PAGES.map((page) => (
          <Route key={page.id} path={page.id} element={<LegalPage page={page} />} />
        ))}
      </Route>
    </Routes>
  )
}
