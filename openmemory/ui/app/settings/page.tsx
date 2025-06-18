'use client';

import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { useRouter } from 'next/navigation';
import { selectIsAuthenticated, selectUser } from '@/store/authSlice';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ApiKeyList from '@/components/settings/ApiKeyList';
import GenerateApiKeyDialog from '@/components/settings/GenerateApiKeyDialog'; // Import the dialog

export default function UserSettingsPage() { // Renamed component for clarity vs an AppSettingsPage
  const router = useRouter();
  const auth = useSelector((state: any) => state.auth); // More robust way to get auth state
  const isAuthenticated = auth.isAuthenticated;
  const user = auth.user;

  // Loading state to prevent flash of unauthenticated content or redirect race conditions
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKeyListTrigger, setRefreshKeyListTrigger] = useState(0); // Trigger for refreshing ApiKeyList

  useEffect(() => {
    // Only check auth status once the auth state has been initialized (not 'idle' or 'loading')
    if (auth.status !== 'idle' && auth.status !== 'loading') {
      if (!isAuthenticated) {
        router.push('/login');
      } else {
        setIsLoading(false);
      }
    }
  }, [isAuthenticated, auth.status, router]);

  // This prevents rendering anything until authentication status is resolved and confirmed
  if (isLoading || auth.status === 'idle' || auth.status === 'loading') {
    return <div className="flex items-center justify-center min-h-screen">Loading settings...</div>;
  }

  // If, after loading, still not authenticated (e.g., token expired, then fetchUser failed)
  // This is a fallback, as useEffect should have redirected.
  if (!isAuthenticated) {
     return <div className="flex items-center justify-center min-h-screen">Redirecting to login...</div>;
  }

  // Dummy functions and state for placeholders, to be implemented with actual components
  // const [apiKeys, setApiKeys] = useState([]);
  // const [isApiKeyListLoading, setIsApiKeyListLoading] = useState(true);
  const refreshApiKeys = () => {
    setRefreshKeyListTrigger(prev => prev + 1); // Increment to trigger useEffect in ApiKeyList
    console.log("SettingsPage: Refreshing API keys triggered");
  };
  // const handleRevokeKey = (keyPrefix: string) => { console.log("Revoking key", keyPrefix); };


  return (
    <div className="container mx-auto py-10">
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Account Settings</CardTitle>
          <CardDescription>Manage your account settings, profile, and API keys.</CardDescription>
        </CardHeader>
        {user && (
          <CardContent>
            <p>Logged in as: <strong>{user.username || user.email}</strong></p>
          </CardContent>
        )}
      </Card>

      <Tabs defaultValue="apiKeys" className="w-full">
        <TabsList className="grid w-full grid-cols-3"> {/* Adjust if more tabs */}
          <TabsTrigger value="apiKeys">API Keys</TabsTrigger>
          <TabsTrigger value="profile" disabled>Profile</TabsTrigger>
          <TabsTrigger value="preferences" disabled>Preferences</TabsTrigger>
        </TabsList>

        <TabsContent value="apiKeys">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>API Keys</CardTitle>
                <CardDescription>
                  Manage API keys for accessing the OpenMemory API programmatically.
                </CardDescription>
              </div>
              {/*
                Placeholder for GenerateApiKeyDialog trigger button
                Will be something like:
              */}
               <GenerateApiKeyDialog onKeyGenerated={refreshApiKeys} />
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                API keys allow external applications to interact with your OpenMemory account.
              </p>
              {/*
                Placeholder for API Key List
                Will be something like:
                <ApiKeyList onRevokeKey={handleRevokeKey} isLoading={isApiKeyListLoading} />
              */}
              <ApiKeyList key={refreshKeyListTrigger} /> {/* Use key prop to force re-mount/re-fetch or pass trigger as prop */}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Manage your profile settings.</CardDescription>
            </CardHeader>
            <CardContent>
              <p>Profile settings will be here.</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="preferences">
          <Card>
            <CardHeader>
              <CardTitle>Preferences</CardTitle>
              <CardDescription>Manage your application preferences.</CardDescription>
            </CardHeader>
            <CardContent>
              <p>Preference settings will be here.</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
