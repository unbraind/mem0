import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { RootState } from './store'; // Assuming RootState is defined in store.ts

// Define the shape of the user object and auth state
interface User {
  id: string; // Assuming UUID is string here
  username: string; // Added username
  email: string;
  name?: string | null;
}

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  accessToken: string | null; // Added accessToken
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: AuthState = {
  isAuthenticated: false,
  user: null,
  accessToken: null, // Added accessToken
  status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
  error: null,
};

// Async Thunks
// TODO: Replace with actual API call logic, error handling, and types for credentials/payloads

// Fetch current user (e.g., on app load)
export const fetchUser = createAsyncThunk('auth/fetchUser', async (_, { rejectWithValue }) => {
  try {
    const response = await fetch('/api/auth/me', { credentials: 'include' });
    if (!response.ok) {
      if (response.status === 401) { // Not authenticated
        return rejectWithValue('Not authenticated');
      }
      const errorData = await response.json();
      return rejectWithValue(errorData.detail || 'Failed to fetch user');
    }
    const data: User = await response.json();
    return data;
  } catch (error: any) {
    return rejectWithValue(error.message || 'Network error');
  }
});

// Login user
export const loginUser = createAsyncThunk(
  'auth/loginUser',
  async (credentials: { username: string; password: string }, { dispatch, rejectWithValue }) => { // Changed email to username
    try {
      const response = await fetch('/api/auth/login', { // Ensure this path is correct, usually /api/auth/login
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials), // Sends {username, password}
        credentials: 'include', // Important for HttpOnly refresh cookie to be set by backend
      });
      if (!response.ok) {
        const errorData = await response.json();
        return rejectWithValue(errorData.detail || 'Login failed');
      }
      const data = await response.json(); // Expects { access_token: "...", token_type: "bearer" }
      // After successful login and getting the access token, fetch user details
      await dispatch(fetchUser());
      return { accessToken: data.access_token }; // Return accessToken to be stored in state
    } catch (error: any) {
      return rejectWithValue(error.message || 'Network error');
    }
  }
);

// Register user
export const registerUser = createAsyncThunk(
  'auth/registerUser',
  // Updated userData to include username
  async (userData: { username: string; email: string; password: string; name?: string }, { rejectWithValue }) => {
    try {
      const response = await fetch('/api/auth/register', { // Ensure this path is correct
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json();
        return rejectWithValue(errorData.detail || 'Registration failed');
      }
      // After registration, typically the user is redirected to login or auto-logged in.
      // For now, just return the registered user data (or success).
      const data: User = await response.json();
      return data;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Network error');
    }
  }
);

// Logout user
export const logoutUser = createAsyncThunk('auth/logoutUser', async (_, { dispatch, rejectWithValue }) => {
  try {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      const errorData = await response.json();
      return rejectWithValue(errorData.detail || 'Logout failed');
    }
    return { success: true };
  } catch (error: any) {
    return rejectWithValue(error.message || 'Network error');
  }
});

// Auth Slice
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearAuthError: (state) => {
      state.error = null;
    },
    setAccessToken: (state, action: PayloadAction<string | null>) => {
      state.accessToken = action.payload;
      // Optionally, you could also infer isAuthenticated from the presence of a token,
      // but usually, it's better to confirm with fetchUser.
      // if (action.payload) state.isAuthenticated = true; else state.isAuthenticated = false;
    },
  },
  extraReducers: (builder) => {
    builder
      // fetchUser
      .addCase(fetchUser.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchUser.fulfilled, (state, action: PayloadAction<User>) => {
        state.status = 'succeeded';
        state.isAuthenticated = true;
        state.user = action.payload;
        state.error = null;
      })
      .addCase(fetchUser.rejected, (state, action) => {
        state.status = 'failed';
        state.isAuthenticated = false;
        state.user = null;
        // Don't set error if it's just "Not authenticated" from 401, that's expected
        if (action.payload !== 'Not authenticated') {
          state.error = action.payload as string;
        }
      })
      // loginUser
      .addCase(loginUser.pending, (state) => {
        state.status = 'loading';
        state.accessToken = null; // Clear previous token
        state.error = null;
      })
      .addCase(loginUser.fulfilled, (state, action: PayloadAction<{ accessToken: string }>) => {
        // fetchUser will handle setting isAuthenticated and user.
        // Here we just store the accessToken.
        state.status = 'succeeded'; // Will be quickly followed by fetchUser states
        state.accessToken = action.payload.accessToken;
        // Do not set isAuthenticated here yet, let fetchUser confirm the user identity with the new token/cookie
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.status = 'failed';
        state.isAuthenticated = false;
        state.user = null;
        state.accessToken = null;
        state.error = action.payload as string;
      })
      // registerUser
      .addCase(registerUser.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(registerUser.fulfilled, (state /*, action: PayloadAction<User>*/) => {
        state.status = 'succeeded'; // Or 'idle' if redirecting to login
        // Optionally, set user and isAuthenticated if registration auto-logs in
        // state.isAuthenticated = true;
        // state.user = action.payload;
      })
      .addCase(registerUser.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload as string;
      })
      // logoutUser
      .addCase(logoutUser.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.status = 'idle';
        state.isAuthenticated = false;
        state.user = null;
        state.accessToken = null; // Clear access token on logout
        state.error = null;
      })
      .addCase(logoutUser.rejected, (state, action) => {
        state.status = 'failed'; // Or 'idle' but with an error
        // state.isAuthenticated and state.user should ideally still be cleared
        state.isAuthenticated = false;
        state.user = null;
        state.accessToken = null; // Clear access token
        state.error = action.payload as string;
      });
  },
});

export const { clearAuthError, setAccessToken } = authSlice.actions; // Export setAccessToken

// Selectors
export const selectIsAuthenticated = (state: RootState) => state.auth.isAuthenticated;
export const selectUser = (state: RootState) => state.auth.user;
export const selectAuthStatus = (state: RootState) => state.auth.status;
export const selectAuthError = (state: RootState) => state.auth.error;
export const selectAccessToken = (state: RootState) => state.auth.accessToken; // Export selectAccessToken

export default authSlice.reducer;
