import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { RootState } from './store'; // Assuming RootState is defined in store.ts

// Define the shape of the user object and auth state
interface User {
  id: string; // Assuming UUID is string here
  email: string;
  name?: string | null;
}

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: AuthState = {
  isAuthenticated: false,
  user: null,
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
  async (credentials: { email: string; password: string }, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json();
        return rejectWithValue(errorData.detail || 'Login failed');
      }
      // Login endpoint might not return the full user object, just a success message.
      // So, dispatch fetchUser to get the user data and set cookie correctly.
      await dispatch(fetchUser());
      // If login *does* return the user object directly and sets cookie, this can be simplified:
      // const userData = await response.json(); return userData.user or similar.
      return { success: true }; // Indicate login process success
    } catch (error: any) {
      return rejectWithValue(error.message || 'Network error');
    }
  }
);

// Register user
export const registerUser = createAsyncThunk(
  'auth/registerUser',
  async (userData: { email: string; password: string; name?: string }, { rejectWithValue }) => {
    try {
      const response = await fetch('/api/auth/register', {
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
    // Could add direct reducers like setUser, clearUser if needed for non-thunk actions
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
        state.error = null;
      })
      .addCase(loginUser.fulfilled, (state) => {
        // User state will be updated by fetchUser dispatched within loginUser or if loginUser returned user data
        // For now, just mark as succeeded if fetchUser is used. If loginUser sets user directly, update here.
        state.status = 'succeeded'; // This might be quickly overwritten by fetchUser's pending/fulfilled
        // If loginUser itself returned user data:
        // state.isAuthenticated = true;
        // state.user = action.payload.user;
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.status = 'failed';
        state.isAuthenticated = false;
        state.user = null;
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
        state.error = null;
      })
      .addCase(logoutUser.rejected, (state, action) => {
        state.status = 'failed'; // Or 'idle' but with an error
        // state.isAuthenticated and state.user should ideally still be cleared
        state.isAuthenticated = false;
        state.user = null;
        state.error = action.payload as string;
      });
  },
});

export const { clearAuthError } = authSlice.actions;

// Selectors
export const selectIsAuthenticated = (state: RootState) => state.auth.isAuthenticated;
export const selectUser = (state: RootState) => state.auth.user;
export const selectAuthStatus = (state: RootState) => state.auth.status;
export const selectAuthError = (state: RootState) => state.auth.error;

export default authSlice.reducer;
