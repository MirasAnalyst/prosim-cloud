import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import AppLayout from './components/layout/AppLayout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import AuthCallback from './pages/AuthCallback';
import InsightsPage from './pages/InsightsPage';
import AboutPage from './pages/AboutPage';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuthStore } from './stores/authStore';
export default function App() {
    const initialize = useAuthStore((s) => s.initialize);
    useEffect(() => {
        initialize();
    }, [initialize]);
    return (_jsx(BrowserRouter, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(HomePage, {}) }), _jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }), _jsx(Route, { path: "/signup", element: _jsx(SignupPage, {}) }), _jsx(Route, { path: "/auth/callback", element: _jsx(AuthCallback, {}) }), _jsx(Route, { path: "/about", element: _jsx(AboutPage, {}) }), _jsx(Route, { path: "/app/insights", element: _jsx(ProtectedRoute, { children: _jsx(InsightsPage, {}) }) }), _jsx(Route, { path: "/app/*", element: _jsx(ProtectedRoute, { children: _jsx(ReactFlowProvider, { children: _jsx(AppLayout, {}) }) }) })] }) }));
}
