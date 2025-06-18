'use client';

import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import { useRouter, usePathname } from 'next/navigation';
import { selectIsAuthenticated, selectAuthStatus } from '../store/authSlice';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const authStatus = useSelector(selectAuthStatus);

  useEffect(() => {
    // If still loading auth status, wait.
    if (authStatus === 'loading' || authStatus === 'idle') {
      return;
    }

    // If auth check is done and user is not authenticated, redirect to login.
    // Preserve the intended path via a query parameter to redirect back after login.
    if (!isAuthenticated) {
      // Avoid redirect loops if already on a public page or if redirecting from login itself
      if (pathname !== '/login' && pathname !== '/register') {
        router.push(`/login?redirect_to=${encodeURIComponent(pathname)}`);
      } else if (pathname === '/login' && isAuthenticated) {
        // If somehow on login page but authenticated, redirect to home
        router.push('/');
      }
    }
  }, [isAuthenticated, authStatus, router, pathname]);

  // Show loading indicator while auth status is loading or idle (initial check)
  // but not if we are on login/register pages already.
  if ((authStatus === 'loading' || authStatus === 'idle') && pathname !== '/login' && pathname !== '/register') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div>Loading user session...</div>
      </div>
    );
  }

  // If authenticated, or if on a public route (like /login, /register themselves, which don't use ProtectedRoute)
  // render children. The check for !isAuthenticated above handles redirection for protected routes.
  // If on a protected route and not authenticated, this part won't be reached due to redirect.
  // If on a protected route and authenticated, render children.
  if (isAuthenticated || pathname === '/login' || pathname === '/register') {
     return <>{children}</>;
  }

  // Fallback for the brief moment before redirection or if logic is bypassed.
  // Or, if we want to strictly only render children when authenticated for protected paths:
  // if (isAuthenticated) return <>{children}</>; else return null; (but redirect handles this)
  return null; // Or a minimal loader, but redirect should occur.
};

export default ProtectedRoute;
