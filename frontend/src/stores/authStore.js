import { create } from 'zustand';
import { supabase } from '../lib/supabase';
export const useAuthStore = create((set) => ({
    user: null,
    session: null,
    loading: true,
    initialize: async () => {
        const { data: { session } } = await supabase.auth.getSession();
        set({ session, user: session?.user ?? null, loading: false });
        supabase.auth.onAuthStateChange((_event, session) => {
            set({ session, user: session?.user ?? null });
        });
    },
    login: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error)
            return { error: error.message };
        return { error: null };
    },
    loginWithGoogle: async () => {
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: `${window.location.origin}/auth/callback` },
        });
        if (error)
            return { error: error.message };
        return { error: null };
    },
    signup: async (email, password) => {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error)
            return { error: error.message };
        return { error: null };
    },
    logout: async () => {
        await supabase.auth.signOut();
        set({ user: null, session: null });
    },
}));
