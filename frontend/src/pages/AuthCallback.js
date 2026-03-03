import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
export default function AuthCallback() {
    const navigate = useNavigate();
    useEffect(() => {
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            if (session) {
                subscription.unsubscribe();
                navigate('/app', { replace: true });
            }
        });
        // Fallback: if auth state doesn't fire within 5s, check session directly
        const timeout = setTimeout(async () => {
            subscription.unsubscribe();
            const { data: { session } } = await supabase.auth.getSession();
            navigate(session ? '/app' : '/login', { replace: true });
        }, 5000);
        return () => {
            subscription.unsubscribe();
            clearTimeout(timeout);
        };
    }, [navigate]);
    return (_jsx("div", { className: "min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950", children: _jsx("p", { className: "text-gray-500 dark:text-gray-400", children: "Confirming your account..." }) }));
}
