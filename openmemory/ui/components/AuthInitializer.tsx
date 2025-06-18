'use client';

import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchUser, selectAuthStatus } from '../store/authSlice';
import { AppDispatch } from '../store/store'; // Ensure AppDispatch is exported from your store

const AuthInitializer = ({ children }: { children: React.ReactNode }) => {
  const dispatch = useDispatch<AppDispatch>();
  const authStatus = useSelector(selectAuthStatus);

  useEffect(() => {
    // Only fetch user if status is idle (e.g., initial load)
    // Or if you want to re-fetch under certain conditions, adjust logic here
    if (authStatus === 'idle') {
      dispatch(fetchUser());
    }
  }, [dispatch, authStatus]);

  // Optional: Show a global loading spinner while initially fetching user
  // This could be more sophisticated, perhaps part of a layout component
  if (authStatus === 'loading' && typeof window !== 'undefined' && window.location.pathname !== '/login' && window.location.pathname !== '/register') {
    // Avoid showing global loader on login/register pages themselves if fetchUser fails and redirects.
    // Or, make this loader more specific to initial app load.
    // A simple approach for now:
    // return <div>Loading application...</div>;
    // For a less intrusive approach, this component might not render anything itself,
    // relying on other components to react to the 'loading' state.
  }

  return <>{children}</>;
};

export default AuthInitializer;
