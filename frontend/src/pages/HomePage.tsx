import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Zap, Target, TrendingUp, Sun, Moon } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';
import FlowsheetMockup from '../components/landing/FlowsheetMockup';

// ── Header ──────────────────────────────────────────────────────────────────

function Header() {
  const [scrolled, setScrolled] = useState(false);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-white/80 dark:bg-gray-950/80 backdrop-blur-lg border-b border-gray-200 dark:border-gray-800'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link
            to="/"
            className="flex items-center gap-2 text-xl font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <img src="/favicon.png" alt="ProSim Cloud" className="w-7 h-7 rounded" />
            ProSim Cloud
          </Link>

          <nav className="hidden md:flex items-center space-x-1">
            <Link to="/app" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors">
              Flowsheet Builder
            </Link>
            <a href="#features" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors">
              Features
            </a>
            <a href="#reviews" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors">
              Reviews
            </a>
            <Link to="/about" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors">
              About
            </Link>
          </nav>

          <div className="flex items-center space-x-2">
            <button
              onClick={toggleTheme}
              className="p-2 text-gray-800 dark:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {user ? (
              <div className="flex items-center space-x-2">
                <Link
                  to="/app"
                  className="text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  Open App
                </Link>
                <button
                  onClick={() => logout()}
                  className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-3 py-2 transition-colors"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  to="/login"
                  className="text-sm px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium"
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  className="text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  Sign up
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

// ── Hero ────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative overflow-hidden bg-white dark:bg-gray-950 pt-32 lg:pt-40 pb-20">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
          <div className="lg:col-span-6 mb-12 lg:mb-0">
            <div className="inline-flex items-center px-3 py-1 rounded-full border border-gray-300 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-400 mb-6">
              AI-Powered Engineering Platform
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 dark:text-white mb-6 leading-[1.1]">
              Create entire plants in{' '}
              <span className="text-blue-600">seconds</span>
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-400 mb-8 max-w-lg leading-relaxed">
              Generate Process Flow Diagrams (PFDs) and unlock industrial optimization insights worth millions—in minutes, not weeks. Join 10,000+ engineers already building the future.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mb-10">
              <Link
                to="/signup"
                className="group inline-flex items-center justify-center px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                Start Building Free
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <a
                href="https://cal.com/miras-muratov-uyocve/30min"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center px-6 py-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                Schedule Demo
              </a>
            </div>
            <div className="flex items-center divide-x divide-gray-200 dark:divide-gray-800 text-sm">
              <div className="pr-6">
                <span className="block text-2xl font-bold text-gray-900 dark:text-white">10,000+</span>
                <span className="text-gray-500 dark:text-gray-400">Active Engineers</span>
              </div>
              <div className="px-6">
                <span className="block text-2xl font-bold text-gray-900 dark:text-white">95%</span>
                <span className="text-gray-500 dark:text-gray-400">Time Saved</span>
              </div>
              <div className="pl-6">
                <span className="block text-2xl font-bold text-gray-900 dark:text-white">$2M+</span>
                <span className="text-gray-500 dark:text-gray-400">Cost Savings</span>
              </div>
            </div>
          </div>
          <div className="lg:col-span-6">
            <FlowsheetMockup />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Logo Bar ────────────────────────────────────────────────────────────────

function LogoBar() {
  return (
    <section className="border-y border-gray-200 dark:border-gray-800 py-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p className="text-xs uppercase tracking-widest text-gray-400 dark:text-gray-500 text-center mb-8">
          Trusted by engineers at leading companies
        </p>
        <div className="grid grid-cols-5 gap-16 items-center max-w-6xl mx-auto">
          <div className="flex items-center justify-center">
            <svg viewBox="0 0 200 28" className="h-10 w-auto" aria-label="ExxonMobil">
              <text x="0" y="22" fontFamily="Arial,Helvetica,sans-serif" fontWeight="700" fontSize="25" letterSpacing="-0.5">
                <tspan fill="#FF0000">Exxon</tspan>
                <tspan fill="#0051A5">Mobil</tspan>
              </text>
            </svg>
          </div>
          <div className="flex items-center justify-center">
            <img src="/logos/shell.svg" alt="Shell" className="h-14 w-auto" />
          </div>
          <div className="flex items-center justify-center">
            <svg viewBox="0 0 110 30" className="h-8 w-auto" aria-label="BASF">
              <rect x="0" y="0" width="110" height="30" rx="2" fill="#004F9E" />
              <text x="55" y="22" fontFamily="Arial,Helvetica,sans-serif" fontWeight="700" fontSize="22" fill="white" textAnchor="middle" letterSpacing="3">BASF</text>
            </svg>
          </div>
          <div className="flex items-center justify-center">
            <img src="/logos/DOW-logo.svg" alt="Dow" className="h-10 w-auto" />
          </div>
          <div className="flex items-center justify-center">
            <img src="/logos/Chevron_Logo.svg.png" alt="Chevron" className="h-14 w-auto object-contain" />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Bento Features ──────────────────────────────────────────────────────────

const features = [
  {
    icon: Zap,
    title: 'Flowsheets in Seconds',
    description: 'Generate complete process flowsheets for oil, gas, chemical, and industrial plants from a single prompt. Go from idea to detailed design in minutes\u2014not weeks.',
    colSpan: 'md:col-span-2',
    rowSpan: 'md:row-span-2',
  },
  {
    icon: Target,
    title: 'Engineer-Level Precision',
    description: 'Built on rigorous thermodynamic models (PR, SRK, NRTL, UNIFAC). Every simulation meets the same standards as manual Aspen HYSYS setups\u2014without the learning curve.',
    colSpan: 'md:col-span-2',
    rowSpan: 'md:row-span-2',
  },
  {
    icon: TrendingUp,
    title: 'Optimize & Scale',
    description: 'Run parametric studies, optimize operating conditions, and scale from concept to production-ready designs with built-in convergence tools.',
    colSpan: 'md:col-span-4',
    rowSpan: '',
  },
];

function BentoFeatures() {
  return (
    <section id="features" className="py-24 bg-white dark:bg-gray-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Everything you need to design at scale
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl">
            From concept to production-ready flowsheets, ProSim Cloud gives engineering teams the tools to move faster with confidence.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className={`${feature.colSpan} ${feature.rowSpan} block bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 transition-colors hover:border-gray-300 dark:hover:border-gray-700`}
              >
                <div className="w-10 h-10 rounded-lg bg-blue-600/10 dark:bg-blue-500/10 flex items-center justify-center mb-4">
                  <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{feature.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{feature.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ── Reviews ─────────────────────────────────────────────────────────────────

const reviews = [
  {
    title: 'A real game-changer for process engineers!',
    content: 'I used to spend days configuring HYSYS\u2014now I generate a complete flowsheet in minutes and my setup time dropped by more than half.',
    author: 'Elena Petrova',
    designation: 'Process Engineer',
  },
  {
    title: 'From concept to flowsheet in minutes.',
    content: 'I went from spending hours on simulation setup to turning a rough concept into a detailed flowsheet in minutes.',
    author: 'Rahul Mehta',
    designation: 'Design Engineer',
  },
  {
    title: 'Seamless for automation workflows.',
    content: 'I used to manually rework every process flow diagram integration\u2014now I auto-generate diagrams and validate control strategies in a single pass.',
    author: 'Lucas Fernandez',
    designation: 'Automation Engineer',
  },
  {
    title: 'Transforms the way I teach chemical engineering.',
    content: "My students struggled with HYSYS's learning curve, but with this platform they practice like professionals from day one.",
    author: 'Dr. Maria Svensson',
    designation: 'Professor of Chemical Engineering',
  },
];

function ReviewCard({ title, content, author, designation }: typeof reviews[0]) {
  const initials = author.split(' ').map((n) => n[0]).join('');
  return (
    <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 transition-colors hover:border-gray-300 dark:hover:border-gray-700">
      <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-3">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-relaxed">&ldquo;{content}&rdquo;</p>
      <div className="flex items-center pt-4 border-t border-gray-100 dark:border-gray-800">
        <div className="w-9 h-9 bg-gray-200 dark:bg-gray-800 rounded-full flex items-center justify-center text-gray-600 dark:text-gray-400 text-sm font-medium mr-3">
          {initials}
        </div>
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-white">{author}</p>
          <p className="text-xs text-gray-500">{designation}</p>
        </div>
      </div>
    </div>
  );
}

function Reviews() {
  return (
    <section id="reviews" className="py-24 bg-gray-50 dark:bg-gray-950 border-t border-gray-200 dark:border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            What Engineers Are Saying
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl">
            Don&apos;t just take our word for it. Here&apos;s what industry professionals are saying about our platform.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reviews.map((review, index) => (
            <ReviewCard key={index} {...review} />
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Get Started CTA ─────────────────────────────────────────────────────────

function GetStarted() {
  return (
    <section className="py-20 bg-white dark:bg-gray-950">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="relative bg-gray-900 rounded-2xl overflow-hidden px-8 py-16 sm:px-16 text-center">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent pointer-events-none" />
          <div className="relative">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
              Start building in minutes
            </h2>
            <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
              5 free designs — no credit card required. Generate production-ready flowsheets with AI.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                to="/signup"
                className="group inline-flex items-center justify-center px-6 py-3 bg-white text-gray-900 font-medium rounded-lg hover:bg-gray-100 transition-colors"
              >
                Get Started
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center justify-center px-6 py-3 border border-gray-600 text-gray-300 font-medium rounded-lg hover:border-gray-500 hover:text-white transition-colors"
              >
                Log In
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────

function Footer() {
  const currentYear = new Date().getFullYear();
  return (
    <footer className="bg-white dark:bg-gray-950 border-t border-gray-200 dark:border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          <div className="col-span-2 md:col-span-1">
            <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
              <img src="/favicon.png" alt="ProSim Cloud" className="w-6 h-6 rounded" />
              ProSim Cloud
            </Link>
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400 max-w-xs">
              AI-powered engineering platform for flowsheets, P&amp;IDs, and process design.
            </p>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-4">Product</h4>
            <ul className="space-y-2">
              <li><Link to="/app" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">Flowsheet Builder</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-4">Account</h4>
            <ul className="space-y-2">
              <li><Link to="/login" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">Sign in</Link></li>
              <li><Link to="/signup" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">Sign up</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-4">Company</h4>
            <ul className="space-y-2">
              <li><Link to="/about" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">About</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-4">Connect</h4>
            <ul className="space-y-2">
              <li><a href="https://www.linkedin.com/in/miras-muratov-7535741b3/" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">LinkedIn</a></li>
              <li><a href="https://github.com/MirasAnalyst" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">GitHub</a></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 pt-6 border-t border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-400 dark:text-gray-500">
            &copy; {currentYear} ProSim Cloud. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}

// ── Home Page ───────────────────────────────────────────────────────────────

export default function HomePage() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return (
    <div className="flex flex-col min-h-screen bg-white dark:bg-gray-950">
      <Header />
      <main>
        <Hero />
        <LogoBar />
        <BentoFeatures />
        <Reviews />
        <GetStarted />
      </main>
      <Footer />
    </div>
  );
}
