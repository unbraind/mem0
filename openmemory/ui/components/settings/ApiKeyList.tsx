'use client';

import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '@/store/store'; // Assuming RootState is correctly typed
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useToast } from "@/components/ui/use-toast"; // For showing errors

// Define a type for the API key data
interface ApiKey {
  id: string; // uuid.UUID from schema
  name: string | null;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at: string; // datetime
  last_used_at: string | null; // datetime
  expires_at: string | null; // datetime
}

interface ApiKeyListProps {
  // onRevokeKey: (keyPrefix: string) => Promise<void>; // To be implemented later
  refreshTrigger?: number; // Optional prop to trigger re-fetch
}

export default function ApiKeyList({ refreshTrigger }: ApiKeyListProps) {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const accessToken = useSelector((state: RootState) => state.auth.accessToken);

  const fetchApiKeys = async () => {
    if (!accessToken) {
      setError("Not authenticated to fetch API keys.");
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/keys', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to fetch API keys: ${response.statusText}`);
      }
      const data: ApiKey[] = await response.json();
      setApiKeys(data);
    } catch (err: any) {
      setError(err.message);
      toast({
        title: "Error fetching API keys",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchApiKeys();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, refreshTrigger]); // Re-fetch if accessToken or refreshTrigger changes

  // Dummy revoke handler for now
  const handleRevoke = async (keyPrefix: string) => {
    if (!accessToken) {
      toast({ title: "Authentication Error", description: "Access token not found.", variant: "destructive" });
      return;
    }
    if (!confirm(`Are you sure you want to revoke API key with prefix ${keyPrefix}? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/keys/${keyPrefix}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        // Try to parse error from backend if available
        let errorDetail = `Failed to revoke API key: ${response.statusText}`;
        try {
            const errorData = await response.json();
            errorDetail = errorData.detail || errorDetail;
        } catch (e) { /* ignore if response is not json */ }
        throw new Error(errorDetail);
      }

      toast({
        title: "API Key Revoked",
        description: `Key with prefix ${keyPrefix} has been revoked.`,
      });
      fetchApiKeys(); // Refresh the list after revoking
    } catch (err: any) {
      toast({
        title: "Error revoking API key",
        description: err.message,
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return <p>Loading API keys...</p>;
  }

  if (error) {
    return <p className="text-red-500">Error: {error}</p>;
  }

  if (apiKeys.length === 0) {
    return <p>No API keys found. Generate one to get started!</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Prefix</TableHead>
          <TableHead>Scopes</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created At</TableHead>
          <TableHead>Expires At</TableHead>
          <TableHead>Last Used</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {apiKeys.map((key) => (
          <TableRow key={key.id}>
            <TableCell>{key.name || '-'}</TableCell>
            <TableCell>{key.key_prefix}</TableCell>
            <TableCell>
              {key.scopes.map(scope => <Badge key={scope} variant="outline" className="mr-1 mb-1">{scope}</Badge>)}
            </TableCell>
            <TableCell>
              <Badge variant={key.is_active ? "default" : "destructive"}>
                {key.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </TableCell>
            <TableCell>{new Date(key.created_at).toLocaleDateString()}</TableCell>
            <TableCell>{key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never'}</TableCell>
            <TableCell>{key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}</TableCell>
            <TableCell>
              <Button variant="destructive" size="sm" onClick={() => handleRevoke(key.key_prefix)}>
                Revoke
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
