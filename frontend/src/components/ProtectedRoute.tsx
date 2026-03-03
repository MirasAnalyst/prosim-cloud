// import { Navigate } from 'react-router-dom';
// import { useAuthStore } from '../stores/authStore';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  // TODO: re-enable auth when Supabase is configured
  // const user = useAuthStore((s) => s.user);
  // const loading = useAuthStore((s) => s.loading);
  // if (loading) {
  //   return (
  //     <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
  //       <p className="text-gray-500 dark:text-gray-400">Loading...</p>
  //     </div>
  //   );
  // }
  // if (!user) {
  //   return <Navigate to="/login" replace />;
  // }
  return <>{children}</>;
}
