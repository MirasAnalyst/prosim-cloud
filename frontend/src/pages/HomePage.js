import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    return (_jsx("header", { className: `fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled
            ? 'bg-white/80 dark:bg-gray-950/80 backdrop-blur-lg border-b border-gray-200 dark:border-gray-800'
            : 'bg-transparent'}`, children: _jsx("div", { className: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8", children: _jsxs("div", { className: "flex items-center justify-between h-16", children: [_jsxs(Link, { to: "/", className: "flex items-center gap-2 text-xl font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors", children: [_jsx("img", { src: "/favicon.png", alt: "ProSim Cloud", className: "w-7 h-7 rounded" }), "ProSim Cloud"] }), _jsxs("nav", { className: "hidden md:flex items-center space-x-1", children: [_jsx(Link, { to: "/app", className: "text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors", children: "Flowsheet Builder" }), _jsx("a", { href: "#features", className: "text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors", children: "Features" }), _jsx("a", { href: "#reviews", className: "text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors", children: "Reviews" }), _jsx(Link, { to: "/about", className: "text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-4 py-2 rounded-md transition-colors", children: "About" })] }), _jsxs("div", { className: "flex items-center space-x-2", children: [_jsx("button", { onClick: toggleTheme, className: "p-2 text-gray-800 dark:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors", children: theme === 'dark' ? _jsx(Sun, { className: "w-4 h-4" }) : _jsx(Moon, { className: "w-4 h-4" }) }), user ? (_jsxs("div", { className: "flex items-center space-x-2", children: [_jsx(Link, { to: "/app", className: "text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium", children: "Open App" }), _jsx("button", { onClick: () => logout(), className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-3 py-2 transition-colors", children: "Sign out" })] })) : (_jsxs("div", { className: "flex items-center space-x-2", children: [_jsx(Link, { to: "/login", className: "text-sm px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium", children: "Sign in" }), _jsx(Link, { to: "/signup", className: "text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium", children: "Sign up" })] }))] })] }) }) }));
}
// ── Hero ────────────────────────────────────────────────────────────────────
function Hero() {
    return (_jsxs("section", { className: "relative overflow-hidden bg-white dark:bg-gray-950 pt-32 lg:pt-40 pb-20", children: [_jsx("div", { className: "absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-blue-500/5 rounded-full blur-3xl pointer-events-none" }), _jsx("div", { className: "relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8", children: _jsxs("div", { className: "lg:grid lg:grid-cols-12 lg:gap-12 items-center", children: [_jsxs("div", { className: "lg:col-span-6 mb-12 lg:mb-0", children: [_jsx("div", { className: "inline-flex items-center px-3 py-1 rounded-full border border-gray-300 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-400 mb-6", children: "AI-Powered Engineering Platform" }), _jsxs("h1", { className: "text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 dark:text-white mb-6 leading-[1.1]", children: ["Create entire plants in", ' ', _jsx("span", { className: "text-blue-600", children: "seconds" })] }), _jsx("p", { className: "text-lg text-gray-600 dark:text-gray-400 mb-8 max-w-lg leading-relaxed", children: "Generate Process Flow Diagrams (PFDs) and unlock industrial optimization insights worth millions\u2014in minutes, not weeks. Join 10,000+ engineers already building the future." }), _jsxs("div", { className: "flex flex-col sm:flex-row gap-3 mb-10", children: [_jsxs(Link, { to: "/signup", className: "group inline-flex items-center justify-center px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors", children: ["Start Building Free", _jsx(ArrowRight, { className: "w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" })] }), _jsx("a", { href: "https://cal.com/miras-muratov-uyocve/30min", target: "_blank", rel: "noopener noreferrer", className: "inline-flex items-center justify-center px-6 py-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors", children: "Schedule Demo" })] }), _jsxs("div", { className: "flex items-center divide-x divide-gray-200 dark:divide-gray-800 text-sm", children: [_jsxs("div", { className: "pr-6", children: [_jsx("span", { className: "block text-2xl font-bold text-gray-900 dark:text-white", children: "10,000+" }), _jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Active Engineers" })] }), _jsxs("div", { className: "px-6", children: [_jsx("span", { className: "block text-2xl font-bold text-gray-900 dark:text-white", children: "95%" }), _jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Time Saved" })] }), _jsxs("div", { className: "pl-6", children: [_jsx("span", { className: "block text-2xl font-bold text-gray-900 dark:text-white", children: "$2M+" }), _jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Cost Savings" })] })] })] }), _jsx("div", { className: "lg:col-span-6", children: _jsx(FlowsheetMockup, {}) })] }) })] }));
}
// ── Logo Bar ────────────────────────────────────────────────────────────────
function LogoBar() {
    return (_jsx("section", { className: "border-y border-gray-200 dark:border-gray-800 py-10", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8", children: [_jsx("p", { className: "text-xs uppercase tracking-widest text-gray-400 dark:text-gray-500 text-center mb-8", children: "Trusted by engineers at leading companies" }), _jsxs("div", { className: "grid grid-cols-5 gap-16 items-center max-w-6xl mx-auto", children: [_jsx("div", { className: "flex items-center justify-center", children: _jsx("svg", { viewBox: "0 0 200 28", className: "h-10 w-auto", "aria-label": "ExxonMobil", children: _jsxs("text", { x: "0", y: "22", fontFamily: "Arial,Helvetica,sans-serif", fontWeight: "700", fontSize: "25", letterSpacing: "-0.5", children: [_jsx("tspan", { fill: "#FF0000", children: "Exxon" }), _jsx("tspan", { fill: "#0051A5", children: "Mobil" })] }) }) }), _jsx("div", { className: "flex items-center justify-center", children: _jsx("img", { src: "/logos/shell.svg", alt: "Shell", className: "h-14 w-auto" }) }), _jsx("div", { className: "flex items-center justify-center", children: _jsxs("svg", { viewBox: "0 0 110 30", className: "h-8 w-auto", "aria-label": "BASF", children: [_jsx("rect", { x: "0", y: "0", width: "110", height: "30", rx: "2", fill: "#004F9E" }), _jsx("text", { x: "55", y: "22", fontFamily: "Arial,Helvetica,sans-serif", fontWeight: "700", fontSize: "22", fill: "white", textAnchor: "middle", letterSpacing: "3", children: "BASF" })] }) }), _jsx("div", { className: "flex items-center justify-center", children: _jsx("img", { src: "/logos/DOW-logo.svg", alt: "Dow", className: "h-10 w-auto" }) }), _jsx("div", { className: "flex items-center justify-center", children: _jsx("img", { src: "/logos/Chevron_Logo.svg.png", alt: "Chevron", className: "h-14 w-auto object-contain" }) })] })] }) }));
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
    return (_jsx("section", { id: "features", className: "py-24 bg-white dark:bg-gray-950", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8", children: [_jsxs("div", { className: "mb-16", children: [_jsx("h2", { className: "text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4", children: "Everything you need to design at scale" }), _jsx("p", { className: "text-lg text-gray-600 dark:text-gray-400 max-w-2xl", children: "From concept to production-ready flowsheets, ProSim Cloud gives engineering teams the tools to move faster with confidence." })] }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-4 gap-4", children: features.map((feature) => {
                        const Icon = feature.icon;
                        return (_jsxs("div", { className: `${feature.colSpan} ${feature.rowSpan} block bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 transition-colors hover:border-gray-300 dark:hover:border-gray-700`, children: [_jsx("div", { className: "w-10 h-10 rounded-lg bg-blue-600/10 dark:bg-blue-500/10 flex items-center justify-center mb-4", children: _jsx(Icon, { className: "w-5 h-5 text-blue-600 dark:text-blue-400" }) }), _jsx("h3", { className: "text-lg font-semibold text-gray-900 dark:text-white mb-2", children: feature.title }), _jsx("p", { className: "text-sm text-gray-600 dark:text-gray-400 leading-relaxed", children: feature.description })] }, feature.title));
                    }) })] }) }));
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
function ReviewCard({ title, content, author, designation }) {
    const initials = author.split(' ').map((n) => n[0]).join('');
    return (_jsxs("div", { className: "bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 transition-colors hover:border-gray-300 dark:hover:border-gray-700", children: [_jsx("h3", { className: "text-base font-semibold text-gray-900 dark:text-white mb-3", children: title }), _jsxs("p", { className: "text-sm text-gray-600 dark:text-gray-400 mb-6 leading-relaxed", children: ["\u201C", content, "\u201D"] }), _jsxs("div", { className: "flex items-center pt-4 border-t border-gray-100 dark:border-gray-800", children: [_jsx("div", { className: "w-9 h-9 bg-gray-200 dark:bg-gray-800 rounded-full flex items-center justify-center text-gray-600 dark:text-gray-400 text-sm font-medium mr-3", children: initials }), _jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-gray-900 dark:text-white", children: author }), _jsx("p", { className: "text-xs text-gray-500", children: designation })] })] })] }));
}
function Reviews() {
    return (_jsx("section", { id: "reviews", className: "py-24 bg-gray-50 dark:bg-gray-950 border-t border-gray-200 dark:border-gray-800", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8", children: [_jsxs("div", { className: "mb-12", children: [_jsx("h2", { className: "text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4", children: "What Engineers Are Saying" }), _jsx("p", { className: "text-lg text-gray-600 dark:text-gray-400 max-w-2xl", children: "Don't just take our word for it. Here's what industry professionals are saying about our platform." })] }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: reviews.map((review, index) => (_jsx(ReviewCard, { ...review }, index))) })] }) }));
}
// ── Get Started CTA ─────────────────────────────────────────────────────────
function GetStarted() {
    return (_jsx("section", { className: "py-20 bg-white dark:bg-gray-950", children: _jsx("div", { className: "max-w-5xl mx-auto px-4 sm:px-6 lg:px-8", children: _jsxs("div", { className: "relative bg-gray-900 rounded-2xl overflow-hidden px-8 py-16 sm:px-16 text-center", children: [_jsx("div", { className: "absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent pointer-events-none" }), _jsxs("div", { className: "relative", children: [_jsx("h2", { className: "text-3xl sm:text-4xl font-bold text-white mb-4", children: "Start building in minutes" }), _jsx("p", { className: "text-gray-400 text-lg mb-8 max-w-xl mx-auto", children: "5 free designs \u2014 no credit card required. Generate production-ready flowsheets with AI." }), _jsxs("div", { className: "flex flex-col sm:flex-row gap-3 justify-center", children: [_jsxs(Link, { to: "/signup", className: "group inline-flex items-center justify-center px-6 py-3 bg-white text-gray-900 font-medium rounded-lg hover:bg-gray-100 transition-colors", children: ["Get Started", _jsx(ArrowRight, { className: "w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" })] }), _jsx(Link, { to: "/login", className: "inline-flex items-center justify-center px-6 py-3 border border-gray-600 text-gray-300 font-medium rounded-lg hover:border-gray-500 hover:text-white transition-colors", children: "Log In" })] })] })] }) }) }));
}
// ── Footer ──────────────────────────────────────────────────────────────────
function Footer() {
    const currentYear = new Date().getFullYear();
    return (_jsx("footer", { className: "bg-white dark:bg-gray-950 border-t border-gray-200 dark:border-gray-800", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12", children: [_jsxs("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-8", children: [_jsxs("div", { className: "col-span-2 md:col-span-1", children: [_jsxs(Link, { to: "/", className: "flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white", children: [_jsx("img", { src: "/favicon.png", alt: "ProSim Cloud", className: "w-6 h-6 rounded" }), "ProSim Cloud"] }), _jsx("p", { className: "mt-3 text-sm text-gray-500 dark:text-gray-400 max-w-xs", children: "AI-powered engineering platform for flowsheets, P&IDs, and process design." })] }), _jsxs("div", { children: [_jsx("h4", { className: "text-sm font-medium text-gray-900 dark:text-white mb-4", children: "Product" }), _jsx("ul", { className: "space-y-2", children: _jsx("li", { children: _jsx(Link, { to: "/app", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "Flowsheet Builder" }) }) })] }), _jsxs("div", { children: [_jsx("h4", { className: "text-sm font-medium text-gray-900 dark:text-white mb-4", children: "Account" }), _jsxs("ul", { className: "space-y-2", children: [_jsx("li", { children: _jsx(Link, { to: "/login", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "Sign in" }) }), _jsx("li", { children: _jsx(Link, { to: "/signup", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "Sign up" }) })] })] }), _jsxs("div", { children: [_jsx("h4", { className: "text-sm font-medium text-gray-900 dark:text-white mb-4", children: "Company" }), _jsx("ul", { className: "space-y-2", children: _jsx("li", { children: _jsx(Link, { to: "/about", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "About" }) }) })] }), _jsxs("div", { children: [_jsx("h4", { className: "text-sm font-medium text-gray-900 dark:text-white mb-4", children: "Connect" }), _jsxs("ul", { className: "space-y-2", children: [_jsx("li", { children: _jsx("a", { href: "https://www.linkedin.com/in/miras-muratov-7535741b3/", target: "_blank", rel: "noopener noreferrer", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "LinkedIn" }) }), _jsx("li", { children: _jsx("a", { href: "https://github.com/MirasAnalyst", target: "_blank", rel: "noopener noreferrer", className: "text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors", children: "GitHub" }) })] })] })] }), _jsx("div", { className: "mt-12 pt-6 border-t border-gray-200 dark:border-gray-800", children: _jsxs("p", { className: "text-sm text-gray-400 dark:text-gray-500", children: ["\u00A9 ", currentYear, " ProSim Cloud. All rights reserved."] }) })] }) }));
}
// ── Home Page ───────────────────────────────────────────────────────────────
export default function HomePage() {
    const theme = useThemeStore((s) => s.theme);
    useEffect(() => {
        document.documentElement.classList.toggle('dark', theme === 'dark');
    }, [theme]);
    return (_jsxs("div", { className: "flex flex-col min-h-screen bg-white dark:bg-gray-950", children: [_jsx(Header, {}), _jsxs("main", { children: [_jsx(Hero, {}), _jsx(LogoBar, {}), _jsx(BentoFeatures, {}), _jsx(Reviews, {}), _jsx(GetStarted, {})] }), _jsx(Footer, {})] }));
}
