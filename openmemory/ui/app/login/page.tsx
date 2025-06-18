'use client';

import { useState, FormEvent, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useRouter } from 'next/navigation';
import { loginUser, selectAuthStatus, selectAuthError, selectIsAuthenticated, clearAuthError } from '../../store/authSlice';
import { AppDispatch } from '../../store/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

export default function LoginPage() {
  const dispatch = useDispatch<AppDispatch>();
  const router = useRouter();
  const authStatus = useSelector(selectAuthStatus);
  const authError = useSelector(selectAuthError);
  const isAuthenticated = useSelector(selectIsAuthenticated);

  const [username, setUsername] = useState(''); // Changed from email to username
  const [password, setPassword] = useState('');

  useEffect(() => {
    // Redirect if already authenticated
    if (isAuthenticated) {
      router.push('/'); // Redirect to dashboard or home page
    }
    // Clear any previous errors when component mounts or auth state changes
    dispatch(clearAuthError());
  }, [isAuthenticated, router, dispatch]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    dispatch(clearAuthError()); // Clear previous errors
    const resultAction = await dispatch(loginUser({ username, password })); // Changed email to username
    if (loginUser.fulfilled.match(resultAction)) {
      // Login thunk now dispatches fetchUser, so redirection is handled by useEffect
      // router.push('/'); // Or whatever your main dashboard page is
    }
    // Error handling is managed by displaying authError from the slice
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Login</CardTitle>
          <CardDescription>Enter your credentials to access your account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                placeholder="yourusername"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={authStatus === 'loading'}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={authStatus === 'loading'}
              />
            </div>
            {authError && (
              <p className="text-sm text-red-500">{authError}</p>
            )}
            <Button type="submit" className="w-full" disabled={authStatus === 'loading'}>
              {authStatus === 'loading' ? 'Logging in...' : 'Login'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="text-sm">
          Don&apos;t have an account? <a href="/register" className="ml-1 font-semibold text-primary hover:underline">Register</a>
        </CardFooter>
      </Card>
    </div>
  );
}
