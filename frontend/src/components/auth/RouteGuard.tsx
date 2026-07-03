'use client';

import { useAuthStore } from '../../stores/auth';
import { useRouter } from 'next/navigation';
import { useEffect, ReactNode, useState } from 'react';

interface RouteGuardProps {
  allowedRoles: ('admin' | 'operator' | 'reader')[];
  children: ReactNode;
}

export function RouteGuard({ allowedRoles, children }: RouteGuardProps) {
  const { user, accessToken } = useAuthStore();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted) {
      if (!accessToken) {
        router.push('/login');
      } else if (user && !allowedRoles.includes(user.role)) {
        router.push('/403');
      }
    }
  }, [mounted, accessToken, user, router, allowedRoles]);

  if (!mounted || !accessToken || (user && !allowedRoles.includes(user.role))) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-200">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mx-auto mb-4"></div>
          <p className="text-sm font-medium">Verifying Access...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
