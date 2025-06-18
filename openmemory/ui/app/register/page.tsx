'use client';

import { useState, FormEvent, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useRouter } from 'next/navigation';
import { registerUser, selectAuthStatus, selectAuthError, clearAuthError } from '../../store/authSlice';
import { AppDispatch } from '../../store/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

export default function RegisterPage() {
  const dispatch = useDispatch<AppDispatch>();
  const router = useRouter();
  const authStatus = useSelector(selectAuthStatus);
  const authError = useSelector(selectAuthError);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // Optional: Add name field if your UserCreate schema and backend support it
  // const [name, setName] = useState('');

  useEffect(() => {
    // Clear any previous errors when component mounts
    dispatch(clearAuthError());
  }, [dispatch]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    dispatch(clearAuthError());
    // const userData = { email, password, name }; // Include name if using
    const userData = { email, password };
    const resultAction = await dispatch(registerUser(userData));

    if (registerUser.fulfilled.match(resultAction)) {
      // Handle successful registration
      // e.g., show a success message and redirect to login, or auto-login by dispatching loginUser
      alert('Registration successful! Please login.'); // Simple alert for now
      router.push('/login');
    }
    // Error handling is managed by displaying authError from the slice
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Register</CardTitle>
          <CardDescription>Create a new account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Optional: Name field
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                type="text"
                placeholder="Your Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={authStatus === 'loading'}
              />
            </div>
            */}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="m@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
              {authStatus === 'loading' ? 'Registering...' : 'Register'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="text-sm">
          Already have an account? <a href="/login" className="ml-1 font-semibold text-primary hover:underline">Login</a>
        </CardFooter>
      </Card>
    </div>
  );
}
