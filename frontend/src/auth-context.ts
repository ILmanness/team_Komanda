import { createContext, useContext } from 'react';
import type { User } from './api';

type AuthState = { user: User | null; checking: boolean; openAuth: () => void; updateUser: (user: User) => void };

export const AuthContext = createContext<AuthState>({
  user: null, checking: false, openAuth: () => undefined, updateUser: () => undefined,
});

export function useAuth() {
  return useContext(AuthContext);
}
