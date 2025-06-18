'use client';

import { useState } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '@/store/store';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from "@/components/ui/use-toast";
import { CopyIcon } from 'lucide-react'; // Assuming lucide-react is used

interface GenerateApiKeyDialogProps {
  onKeyGenerated: () => void; // Callback to refresh the list
}

interface NewApiKeyInfo {
  api_key: string;
  id: string;
  name: string | null;
  key_prefix: string;
  scopes: string[];
  // Add other fields if returned by backend and needed for display
}

export default function GenerateApiKeyDialog({ onKeyGenerated }: GenerateApiKeyDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [keyName, setKeyName] = useState('');
  // TODO: Add state for scopes and expires_at if implementing those fields
  // const [scopesInput, setScopesInput] = useState('');
  // const [expiresAt, setExpiresAt] = useState<string | undefined>(undefined);

  const [isLoading, setIsLoading] = useState(false);
  const [newApiKeyInfo, setNewApiKeyInfo] = useState<NewApiKeyInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();
  const accessToken = useSelector((state: RootState) => state.auth.accessToken);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!accessToken) {
      setError("Authentication token not found. Please log in again.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setNewApiKeyInfo(null);

    const payload: { name?: string; scopes?: string[]; expires_at?: string } = {};
    if (keyName.trim()) {
      payload.name = keyName.trim();
    }
    // if (scopesInput.trim()) {
    //   payload.scopes = scopesInput.split(',').map(s => s.trim()).filter(s => s);
    // }
    // if (expiresAt) {
    //   payload.expires_at = new Date(expiresAt).toISOString();
    // }

    try {
      const response = await fetch('/api/v1/keys', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Failed to generate API key: ${response.statusText}`);
      }
      setNewApiKeyInfo(data as NewApiKeyInfo); // data should be ApiKeyCreateResponse
      onKeyGenerated(); // Refresh the list in the parent component
      // Keep dialog open to show the key
    } catch (err: any) {
      setError(err.message);
      toast({
        title: "Error generating API key",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyToClipboard = () => {
    if (newApiKeyInfo?.api_key) {
      navigator.clipboard.writeText(newApiKeyInfo.api_key)
        .then(() => {
          toast({ title: "API Key Copied!", description: "The key has been copied to your clipboard." });
        })
        .catch(err => {
          toast({ title: "Copy Failed", description: "Could not copy key to clipboard.", variant: "destructive" });
          console.error('Failed to copy text: ', err);
        });
    }
  };

  const closeDialog = () => {
    setIsOpen(false);
    setNewApiKeyInfo(null); // Clear key info when dialog closes
    setError(null);
    setKeyName(''); // Reset form
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      setIsOpen(open);
      if (!open) closeDialog(); // Reset state when dialog is closed
    }}>
      <DialogTrigger asChild>
        <Button>Generate New Key</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[525px]">
        <DialogHeader>
          <DialogTitle>{newApiKeyInfo ? 'API Key Generated' : 'Generate New API Key'}</DialogTitle>
          {!newApiKeyInfo && (
            <DialogDescription>
              Configure and generate a new API key. The key will be displayed once after generation.
            </DialogDescription>
          )}
        </DialogHeader>
        {newApiKeyInfo ? (
          <div className="space-y-4 py-4">
            <p className="text-sm text-destructive">
              This is the only time you will see this API key. Store it securely.
            </p>
            <div className="flex items-center space-x-2">
              <Input value={newApiKeyInfo.api_key} readOnly className="font-mono"/>
              <Button variant="outline" size="icon" onClick={handleCopyToClipboard}>
                <CopyIcon className="h-4 w-4" />
              </Button>
            </div>
            <div>
              <p><strong>Name:</strong> {newApiKeyInfo.name || '-'}</p>
              <p><strong>Prefix:</strong> {newApiKeyInfo.key_prefix}</p>
              <p><strong>Scopes:</strong> {newApiKeyInfo.scopes.join(', ')}</p>
            </div>
            <Button onClick={closeDialog} className="w-full">Close</Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="keyName">Key Name (Optional)</Label>
              <Input
                id="keyName"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="e.g., My Test Application"
                disabled={isLoading}
              />
            </div>
            {/* TODO: Add Scopes and Expires At fields if needed
            <div>
              <Label htmlFor="keyScopes">Scopes (Optional, comma-separated)</Label>
              <Input id="keyScopes" value={scopesInput} onChange={(e) => setScopesInput(e.target.value)} placeholder="e.g., memories:read,memories:write" disabled={isLoading} />
            </div>
            <div>
              <Label htmlFor="keyExpiresAt">Expires At (Optional)</Label>
              <Input id="keyExpiresAt" type="datetime-local" onChange={(e) => setExpiresAt(e.target.value)} disabled={isLoading} />
            </div>
            */}
            {error && <p className="text-sm text-red-500">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog} disabled={isLoading}>
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? 'Generating...' : 'Generate Key'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
