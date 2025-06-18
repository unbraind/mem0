import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { store } from '../store/store'; // Adjust path as needed to your Redux store
import { setAccessToken, logoutUser, selectAccessToken } from '../store/authSlice'; // Adjust path

const apiClient = axios.create({
  baseURL: '/api', // Assuming all API calls are prefixed with /api
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add the access token to headers
apiClient.interceptors.request.use(
  (config) => {
    const token = selectAccessToken(store.getState()); // Get token from Redux store
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response error interceptor to handle 401 and refresh token
let isRefreshing = false;
let failedQueue: Array<{ resolve: (value?: any) => void; reject: (error?: any) => void }> = [];

const processQueue = (error: AxiosError | null, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // If already refreshing, add this request to a queue
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
        .then(token => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return apiClient(originalRequest);
        })
        .catch(err => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshResponse = await axios.post('/api/auth/refresh', {}, {
          // No explicit token needed here, relies on HttpOnly refresh token cookie
          // baseURL should be set if this axios instance doesn't have it by default for /api
        });

        const newAccessToken = refreshResponse.data.access_token;
        store.dispatch(setAccessToken(newAccessToken)); // Dispatch action to update token in Redux

        if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        }
        processQueue(null, newAccessToken); // Process queued requests with new token
        return apiClient(originalRequest); // Retry original request
      } catch (refreshError: any) {
        store.dispatch(logoutUser()); // If refresh fails, logout user
        processQueue(refreshError, null); // Reject queued requests
        // Optionally redirect to login page here or let UI components handle it based on auth state
        // window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
