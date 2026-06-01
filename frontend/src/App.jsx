import Topbar from './components/Topbar'
import Footer from './components/Footer'
import DashboardPage from './pages/DashboardPage'
import InjectPage from './pages/InjectPage'
import PromptPage from './pages/PromptPage'
import ModelPage from './pages/ModelPage'
import ResultsPage from './pages/ResultsPage'
import SemanticOSPage from './pages/SemanticOSPage'
import useStore from './store'

// Semantic OS is now the single unified surface (Observatory folded in with a scope selector).
const PAGES = [DashboardPage, InjectPage, PromptPage, ModelPage, ResultsPage, SemanticOSPage]

export default function App() {
  const currentStep = useStore((s) => s.currentStep)
  const Page = PAGES[currentStep] || InjectPage

  return (
    <div className="min-h-screen font-sora text-t1" style={{ background: '#e8ecf4' }}>
      <Topbar />
      <div className="app-shell pt-14">
        <Page />
      </div>
      <Footer />
    </div>
  )
}
